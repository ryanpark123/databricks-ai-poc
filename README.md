# Databricks + Claude Agentic POCs

Two proof-of-concept agents built for Databricks, using Claude to add a natural-language
reasoning layer on top of PySpark/Spark SQL. Built as portfolio pieces to demonstrate
PM + technical range with Databricks and AI agent tooling.

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
