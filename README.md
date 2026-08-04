# Databricks + Claude Agentic POCs

Two proof-of-concept agents built for Databricks, using Claude to add a natural-language
reasoning layer on top of PySpark/Spark SQL. Built as portfolio pieces to demonstrate
PM + technical range with Databricks and AI agent tooling.


### AI-generated data quality report
Real profiling stats fed into Claude, returned as a prioritized, actionable report:

![Data quality report]
**📊 Data Quality Report: `sales_transactions`**
**Severity: Medium**

---

**Key Findings:**

1. **🟡 Revenue nulls (3.1%)** — 155 of 5,000 rows are missing `revenue` values. These transactions are silently excluded from any SUM/AVG aggregations, meaning current revenue totals are likely understated. Needs immediate triage to determine if this is a pipeline gap or legitimate (e.g., comped orders).

2. **🟡 Low customer-to-transaction ratio** — 798 distinct `customer_email` values across 5,000 rows means an average of ~6.3 transactions per customer. Worth confirming this is expected behavior and not the result of email deduplication failures or shared accounts inflating repeat-purchase metrics.

3. **🟡 Sparse date coverage** — Only 211 distinct `order_date` values across 5,000 rows. Depending on the expected date range, this could indicate missing data for certain periods or suspicious clustering. Confirm whether all expected business days are represented.

4. **🟢 transaction_id looks clean** — 5,000 rows, 5,000 distinct IDs, min=0/max=4999 with no nulls. Sequential and complete. No issues.

---

**Recommended Next Steps:**

1. **Investigate the 155 null `revenue` rows** — Pull them by `product`, `region`, and `order_date` to identify if the nulls are concentrated (e.g., one product, one date range), which would point to a specific upstream ingestion failure.

2. **Audit `order_date` distribution** — Run a daily/weekly transaction count and flag any gaps. If the dataset is supposed to cover a continuous period, missing dates could indicate dropped data.

3. **Add a `revenue` not-null check and a min > 0 check to your pipeline contract** — Given `revenue` is a core business metric, this should be a blocking quality gate, not a silent miss.

### Natural language to SQL
"What were the top 5 products by total revenue?" → correct SQL on the first attempt:

![NL to SQL]
<img width="1456" height="813" alt="image" src="https://github.com/user-attachments/assets/3e3cc83e-304d-4630-a804-84f379a4537f" />
<img width="469" height="264" alt="Screenshot 2026-08-03 at 9 09 24 PM" src="https://github.com/user-attachments/assets/b72fd492-ee00-4654-8fcd-f96632d314e9" />
<img width="1536" height="728" alt="image" src="https://github.com/user-attachments/assets/64f82c41-40d1-42c6-8b6e-b38be1f30985" />


### Eval harness results
15/15 questions answered correctly against ground-truth SQL — includes a fixed
bug in the comparison logic (see commit history) where the harness initially
compared by column name rather than position, undercounting accuracy at 73%.

![Eval results]
<img width="780" height="447" alt="Screenshot 2026-08-03 at 9 10 09 PM" src="https://github.com/user-attachments/assets/3016c18c-6dbf-4127-b9f5-a66b2539d976" />


## Projects

### 1. AI-Powered Data Quality Agent (`notebooks/01_data_quality_agent.py`)
Profiles a Delta table (nulls, dtype drift, cardinality, outliers vs. a baseline),
then sends the stats to Claude, which returns a plain-English data quality report
with a severity rating and recommended next steps — the kind of thing a data team
lead could paste into a Slack channel.

### 2. Natural Language → SQL Assistant (`notebooks/02_nl_to_sql_assistant.py`)
Takes a plain-English question ("what were our top 5 products by revenue last month?"),
uses Claude to generate the corresponding Spark SQL against a known schema, executes
it safely (read-only, row-limited), and returns both the results and a plain-English
explanation of what the query does.

**Self-correction loop:** if the generated SQL errors out, the actual Spark error is
fed back to Claude, which gets up to 3 attempts to fix it — this is an agentic retry
loop, not a single-shot prompt (`src/nl_to_sql_agent.py::generate_sql_with_retry`).

### 3. Eval harness (`notebooks/03_run_eval.py`, `eval/`)
A 15-question eval set (`eval/eval_questions.json`) with hand-written ground-truth SQL
for each question. The harness runs the agent on every question, compares its result
against the ground truth (order-independent, with numeric tolerance), and logs
accuracy + retry stats to a Delta table (`nl_to_sql_eval_runs`) so you can track
whether accuracy improves or regresses as you change the prompt.

## Repo structure
```
databricks-ai-poc/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── src/
│   ├── claude_client.py       # shared Claude API wrapper
│   ├── data_quality_agent.py  # profiling + report generation logic
│   └── nl_to_sql_agent.py     # NL→SQL generation + safe execution
├── notebooks/
│   ├── 01_data_quality_agent.py     # Databricks notebook (source format)
│   ├── 02_nl_to_sql_assistant.py    # Databricks notebook (source format)
│   └── 03_run_eval.py               # runs eval/ and logs accuracy to Delta
├── eval/
│   ├── eval_questions.json          # 15 questions + ground-truth reference SQL
│   └── run_eval.py                  # scoring logic
└── sample_data/
    └── generate_sample_data.py      # creates a demo Delta table if you don't have one
```

## Setup

1. Get an Anthropic API key from https://console.anthropic.com
2. In Databricks: **Settings → Secrets** (or `databricks secrets create-scope`) and store
   the key as a secret, e.g. scope `claude-poc`, key `anthropic_api_key`.
3. Import the two notebooks in `notebooks/` into your Databricks workspace
   (Workspace → Import → File, select "Source" format).
4. Attach a cluster with `anthropic` installed (`%pip install anthropic` in the first cell,
   already included in the notebooks).
5. Run `sample_data/generate_sample_data.py` first if you want to test against demo data
   rather than your own table.

## Why these two

Both agents follow the same pattern — deterministic Spark work does the heavy lifting,
Claude sits on top to translate between structured data and plain English — which is
the core pattern most "AI on top of the lakehouse" product asks boil down to.
