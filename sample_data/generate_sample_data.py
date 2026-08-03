# Databricks notebook source
# MAGIC %md
# MAGIC # Generate Sample Data
# MAGIC Creates a demo `sales_transactions` Delta table so you can test both agents
# MAGIC without needing your own dataset. Run this once before the other two notebooks.

# COMMAND ----------

from pyspark.sql import Row
import random
from datetime import date, timedelta

random.seed(42)
products = ["Widget A", "Widget B", "Gadget X", "Gadget Y", "Doohickey Z"]
regions = ["West", "East", "Central", "South"]

rows = []
start = date(2026, 1, 1)
for i in range(5000):
    d = start + timedelta(days=random.randint(0, 210))
    rows.append(Row(
        transaction_id=i,
        order_date=d,
        product=random.choice(products),
        region=random.choice(regions),
        revenue=round(random.uniform(20, 900), 2) if random.random() > 0.03 else None,  # inject some nulls
        quantity=random.randint(1, 10),
        customer_email=f"cust{random.randint(1, 800)}@example.com",
    ))

df = spark.createDataFrame(rows)
df.write.mode("overwrite").saveAsTable("sales_transactions")

display(df.limit(10))
print(f"Created sales_transactions with {df.count()} rows.")
