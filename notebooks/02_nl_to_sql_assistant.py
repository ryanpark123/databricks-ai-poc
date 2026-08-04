# Databricks notebook source
# MAGIC %md
# MAGIC # Natural Language -> SQL Assistant
# MAGIC Ask a plain-English question, Claude generates the Spark SQL, we run it
# MAGIC read-only, and Claude explains the result.

# COMMAND ----------

# MAGIC %pip install --upgrade anthropic typing_extensions

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

import sys
sys.path.append("/Workspace/Users/parkryan844@gmail.com/databricks-ai-poc/src")  # adjust to your repo path

from claude_client import get_client
from nl_to_sql_agent import get_schema_description, generate_sql_with_retry, explain_results

# COMMAND ----------

TABLE_NAME = "sales_transactions"

api_key = dbutils.secrets.get(scope="claude-poc", key="anthropic_api_key")
client = get_client(api_key)
schema_description = get_schema_description(spark, TABLE_NAME)
print(schema_description)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Ask a question
# MAGIC Try things like: *"What were total revenue and quantity by region last month?"*
# MAGIC or *"Which product had the highest average revenue per order?"*

# COMMAND ----------

dbutils.widgets.text("question", "What were the top 5 products by total revenue?")
question = dbutils.widgets.get("question")

# generate_sql_with_retry will self-correct up to 3 times if the SQL errors out,
# feeding the actual Spark error back to Claude on each retry.
outcome = generate_sql_with_retry(client, spark, question, schema_description)

print(f"Success: {outcome['success']} (attempts: {len(outcome['attempts'])})")
for a in outcome["attempts"]:
    if a["status"] == "error":
        print(f"  attempt {a['attempt']} FAILED: {a['error']}")
    else:
        print(f"  attempt {a['attempt']} SUCCEEDED")
print("\nFinal SQL:\n", outcome["sql"])

# COMMAND ----------

if outcome["success"]:
    result_df = outcome["result"]
    display(result_df)
else:
    print("The agent could not produce a working query after all retries. "
          "Check the attempt history above for the underlying errors.")

# COMMAND ----------

if outcome["success"]:
    preview = [row.asDict() for row in result_df.limit(20).collect()]
    explanation = explain_results(client, question, outcome["sql"], preview)
    print(explanation)