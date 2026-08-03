# Databricks notebook source
# MAGIC %md
# MAGIC # AI-Powered Data Quality Agent
# MAGIC Profiles a Delta table, compares against a saved baseline (if one exists), and
# MAGIC asks Claude to turn the raw stats into a plain-English data quality report.

# COMMAND ----------

# MAGIC %pip install anthropic

# COMMAND ----------

import sys
sys.path.append("/Workspace/Repos/<your-repo-path>/databricks-ai-poc/src")  # adjust to your repo path
# Simpler alternative if you're not using Repos: paste the contents of src/*.py
# directly into cells here, or use %run on notebook versions of those files.

from claude_client import get_client
from data_quality_agent import profile_dataframe, diff_profiles, generate_report
import json

# COMMAND ----------

# MAGIC %md
# MAGIC ## Config

# COMMAND ----------

TABLE_NAME = "sales_transactions"
BASELINE_PATH = "/tmp/claude_poc/baseline_profile.json"

api_key = dbutils.secrets.get(scope="claude-poc", key="anthropic_api_key")
client = get_client(api_key)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Profile the table

# COMMAND ----------

df = spark.table(TABLE_NAME)
current_profile = profile_dataframe(df)
print(json.dumps(current_profile, indent=2, default=str))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Compare to baseline (if one exists) and generate the report

# COMMAND ----------

drift = None
try:
    with open(BASELINE_PATH.replace("/tmp/", "/dbfs/tmp/"), "r") as f:
        baseline_profile = json.load(f)
    drift = diff_profiles(current_profile, baseline_profile)
    print("Drift vs baseline:", json.dumps(drift, indent=2))
except FileNotFoundError:
    print("No baseline found yet — this run will become the baseline.")

report = generate_report(client, TABLE_NAME, current_profile, drift)
print(report)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Save this run as the new baseline for next time

# COMMAND ----------

dbutils.fs.mkdirs("/tmp/claude_poc")
with open(BASELINE_PATH.replace("/tmp/", "/dbfs/tmp/"), "w") as f:
    json.dump(current_profile, f, default=str)

print("Baseline updated.")
