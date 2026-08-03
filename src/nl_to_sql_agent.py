"""
Natural Language -> SQL Assistant — takes a plain-English question, asks Claude to
generate Spark SQL against a known schema, runs it read-only with a row limit, and
asks Claude to explain the result in plain English.

Includes a self-correction loop: if the generated SQL errors out, the error message
is fed back to Claude for up to MAX_RETRIES attempts before giving up.
"""

import json
import re

from claude_client import ask_claude

MAX_RETRIES = 3

# Basic guardrail: only allow read-only queries.
DISALLOWED_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|MERGE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)

MAX_ROWS = 200


def get_schema_description(spark, table_name: str) -> str:
    """Return a text description of a table's schema for the prompt."""
    df = spark.table(table_name)
    lines = [f"{f.name} ({f.dataType.simpleString()})" for f in df.schema.fields]
    return f"Table `{table_name}` columns:\n" + "\n".join(lines)


SQL_SYSTEM_PROMPT = (
    "You translate plain-English business questions into a single Spark SQL query. "
    "Only use the columns and table given. Always include a LIMIT clause (max 200). "
    "Return ONLY the raw SQL, no markdown fences, no commentary."
)


def _clean_sql(raw: str) -> str:
    return re.sub(r"^```sql|```$", "", raw.strip(), flags=re.IGNORECASE).strip()


def generate_sql(client, question: str, schema_description: str) -> str:
    """Ask Claude to generate a single read-only Spark SQL query for the question."""
    user_prompt = f"{schema_description}\n\nQuestion: {question}\n\nSQL query:"
    return _clean_sql(ask_claude(client, SQL_SYSTEM_PROMPT, user_prompt))


def generate_sql_with_retry(client, spark, question: str, schema_description: str) -> dict:
    """Generate SQL and execute it, self-correcting on error up to MAX_RETRIES times.

    Returns a dict with the final sql, the result DataFrame (or None on total failure),
    the number of attempts made, and the history of any errors encountered — useful
    both for debugging and as an artifact to show "the agent recovered from a mistake."
    """
    attempts = []
    sql = generate_sql(client, question, schema_description)

    for attempt_num in range(1, MAX_RETRIES + 1):
        try:
            safe_sql = validate_sql(sql)
            result_df = spark.sql(safe_sql)
            result_df.take(1)  # force evaluation so errors surface here, not on display()
            attempts.append({"attempt": attempt_num, "sql": safe_sql, "status": "success"})
            return {"sql": safe_sql, "result": result_df, "attempts": attempts, "success": True}
        except Exception as e:  # noqa: BLE001 - we deliberately want to catch and retry on any Spark error
            error_msg = str(e).split("\n")[0][:500]  # first line, capped length
            attempts.append({"attempt": attempt_num, "sql": sql, "status": "error", "error": error_msg})

            if attempt_num == MAX_RETRIES:
                break

            retry_prompt = (
                f"{schema_description}\n\n"
                f"Question: {question}\n\n"
                f"Your previous SQL attempt failed:\n{sql}\n\n"
                f"Error:\n{error_msg}\n\n"
                "Fix the query and return ONLY the corrected raw SQL."
            )
            sql = _clean_sql(ask_claude(client, SQL_SYSTEM_PROMPT, retry_prompt))

    return {"sql": sql, "result": None, "attempts": attempts, "success": False}


def validate_sql(sql: str) -> None:
    """Raise if the generated SQL contains a write/DDL keyword — read-only guardrail."""
    if DISALLOWED_KEYWORDS.search(sql):
        raise ValueError(f"Generated SQL failed the read-only safety check: {sql}")
    if "limit" not in sql.lower():
        sql_with_limit = f"{sql.rstrip(';')} LIMIT {MAX_ROWS}"
        return sql_with_limit
    return sql


def run_query(spark, sql: str):
    """Execute the validated SQL and return a Spark DataFrame."""
    safe_sql = validate_sql(sql)
    return spark.sql(safe_sql)


def explain_results(client, question: str, sql: str, result_preview: list[dict]) -> str:
    """Ask Claude to explain, in plain English, what the query found."""
    system = (
        "You explain SQL query results to a non-technical stakeholder in 2-4 sentences. "
        "Be concrete: cite actual numbers from the result preview. No SQL jargon."
    )
    user_prompt = (
        f"Original question: {question}\n\n"
        f"SQL run: {sql}\n\n"
        f"Result preview (first rows): {json.dumps(result_preview, default=str)}\n\n"
        "Explain the answer:"
    )
    return ask_claude(client, system, user_prompt)
