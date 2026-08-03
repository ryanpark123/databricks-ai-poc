"""
Eval harness for the NL-to-SQL agent.

For each question in eval_questions.json, we:
  1. Run the agent (generate_sql_with_retry) to get its SQL + result.
  2. Run the human-written reference_sql to get the ground-truth result.
  3. Compare on compare_columns — for grouped/ranked questions we compare the
     *set* of values in the specified column(s) (order-independent, since two
     valid SQL formulations can return rows in a different order); for numeric
     single-value questions we compare within numeric_tolerance.

This doesn't check SQL text similarity (two different queries can be equally
correct) — it checks whether the agent's query produces the right answer.
"""

import json
from pathlib import Path

from claude_client import get_client
from nl_to_sql_agent import get_schema_description, generate_sql_with_retry


def load_questions(path: str) -> list[dict]:
    with open(path, "r") as f:
        return json.load(f)


def _values_for_columns(rows: list[dict], columns: list[str]):
    """Return a comparable, order-independent representation of the rows' values
    in the given columns."""
    return sorted(tuple(round(r[c], 2) if isinstance(r[c], float) else r[c] for c in columns) for r in rows)


def score_question(client, spark, q: dict, table_name: str, schema_description: str) -> dict:
    outcome = generate_sql_with_retry(client, spark, q["question"], schema_description)

    result = {
        "id": q["id"],
        "question": q["question"],
        "agent_sql": outcome["sql"],
        "attempts": len(outcome["attempts"]),
        "agent_executed": outcome["success"],
        "correct": False,
        "notes": "",
    }

    if not outcome["success"]:
        result["notes"] = "Agent SQL never executed successfully."
        return result

    try:
        reference_rows = [r.asDict() for r in spark.sql(q["reference_sql"]).collect()]
        agent_rows = [r.asDict() for r in outcome["result"].collect()]
    except Exception as e:  # noqa: BLE001
        result["notes"] = f"Error collecting rows for comparison: {e}"
        return result

    cols = q["compare_columns"]
    tolerance = q.get("numeric_tolerance", 0)

    try:
        ref_values = _values_for_columns(reference_rows, cols)
        agent_values = _values_for_columns(agent_rows, cols)

        if tolerance and all(isinstance(v, (int, float)) for row in ref_values for v in row):
            # Numeric comparison within tolerance, position-matched after sorting.
            correct = len(ref_values) == len(agent_values) and all(
                abs(r_v - a_v) <= tolerance
                for r_row, a_row in zip(ref_values, agent_values)
                for r_v, a_v in zip(r_row, a_row)
            )
        else:
            correct = ref_values == agent_values

        result["correct"] = correct
        if not correct:
            result["notes"] = f"expected={ref_values[:5]} got={agent_values[:5]}"
    except Exception as e:  # noqa: BLE001
        result["notes"] = f"Error comparing results: {e}"

    return result


def run_eval(client, spark, table_name: str, questions_path: str) -> dict:
    schema_description = get_schema_description(spark, table_name)
    questions = load_questions(questions_path)

    results = [score_question(client, spark, q, table_name, schema_description) for q in questions]

    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    avg_attempts = sum(r["attempts"] for r in results) / total if total else 0
    self_corrected = sum(1 for r in results if r["attempts"] > 1 and r["correct"])

    summary = {
        "total_questions": total,
        "correct": correct,
        "accuracy": round(correct / total, 3) if total else 0,
        "avg_attempts_per_question": round(avg_attempts, 2),
        "questions_needing_self_correction": self_corrected,
    }

    return {"summary": summary, "results": results}
