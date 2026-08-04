# Databricks notebook source
# MAGIC %md
# MAGIC # NL-to-SQL Agent Eval
# MAGIC Runs the 15-question eval set against the NL-to-SQL agent (with its self-correction
# MAGIC retry loop), scores accuracy against ground-truth reference SQL, and logs results to
# MAGIC a Delta table so accuracy can be tracked run over run (e.g. after a prompt change).
# MAGIC
# MAGIC Run `sample_data/generate_sample_data.py` first — this eval set is written against
# MAGIC the `sales_transactions` demo table.

# COMMAND ----------

# MAGIC %pip install --upgrade anthropic typing_extensions

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

import sys
sys.path.append("/Workspace/Users/parkryan844@gmail.com/databricks-ai-poc/src")   # adjust to your repo path
sys.path.append("/Workspace/Users/parkryan844@gmail.com/databricks-ai-poc/eval")  # adjust to your repo path

from claude_client import get_client
from run_eval import run_eval
import json
from datetime import datetime

# COMMAND ----------

TABLE_NAME = "sales_transactions"
QUESTIONS_PATH = "/Workspace/Users/parkryan844@gmail.com/databricks-ai-poc/eval/eval_questions.json"  # adjust
EVAL_LOG_TABLE = "nl_to_sql_eval_runs"

api_key = dbutils.secrets.get(scope="claude-poc", key="anthropic_api_key")
client = get_client(api_key)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Run the eval

# COMMAND ----------

eval_output = run_eval(client, spark, TABLE_NAME, QUESTIONS_PATH)

print(json.dumps(eval_output["summary"], indent=2))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Per-question breakdown

# COMMAND ----------

for r in eval_output["results"]:
    status = "PASS" if r["correct"] else "FAIL"
    print(f"[{status}] {r['id']} ({r['attempts']} attempt(s)): {r['question']}")
    if not r["correct"]:
        print(f"    -> {r['notes']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Log this run to a Delta table
# MAGIC Track accuracy over time — e.g. after you tweak the system prompt, compare this
# MAGIC run's accuracy to the last one. This is the artifact that turns "I called an LLM"
# MAGIC into "I measure whether the LLM is actually right."

# COMMAND ----------

summary = eval_output["summary"]
run_row = spark.createDataFrame([{
    "run_timestamp": datetime.utcnow().isoformat(),
    "total_questions": summary["total_questions"],
    "correct": summary["correct"],
    "accuracy": summary["accuracy"],
    "avg_attempts_per_question": summary["avg_attempts_per_question"],
    "questions_needing_self_correction": summary["questions_needing_self_correction"],
}])

run_row.write.mode("append").saveAsTable(EVAL_LOG_TABLE)

display(spark.table(EVAL_LOG_TABLE).orderBy("run_timestamp", ascending=False))