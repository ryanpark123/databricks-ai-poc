"""
Data Quality Agent — profiles a Spark DataFrame, optionally compares it against
a prior baseline profile, and asks Claude to turn the raw stats into a plain-English
data quality report a non-technical stakeholder could read.
"""

import json
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from claude_client import ask_claude


def profile_dataframe(df: DataFrame) -> dict:
    """Compute per-column null rates, distinct counts, and dtypes for a DataFrame."""
    total_rows = df.count()
    profile = {"row_count": total_rows, "columns": {}}

    for field in df.schema.fields:
        col_name = field.name
        col_type = str(field.dataType)

        null_count = df.filter(F.col(col_name).isNull()).count()
        distinct_count = df.select(col_name).distinct().count()

        col_stats = {
            "dtype": col_type,
            "null_count": null_count,
            "null_rate": round(null_count / total_rows, 4) if total_rows else 0,
            "distinct_count": distinct_count,
        }

        # Numeric columns get basic distribution stats for outlier context.
        if col_type in ("DoubleType()", "IntegerType()", "LongType()", "FloatType()"):
            stats = df.select(
                F.min(col_name).alias("min"),
                F.max(col_name).alias("max"),
                F.avg(col_name).alias("avg"),
                F.stddev(col_name).alias("stddev"),
            ).collect()[0]
            col_stats.update({
                "min": stats["min"],
                "max": stats["max"],
                "avg": round(stats["avg"], 2) if stats["avg"] is not None else None,
                "stddev": round(stats["stddev"], 2) if stats["stddev"] is not None else None,
            })

        profile["columns"][col_name] = col_stats

    return profile


def diff_profiles(current: dict, baseline: dict) -> dict:
    """Compare current profile to a baseline to flag schema drift and shifting null rates."""
    drift = {"new_columns": [], "removed_columns": [], "dtype_changes": [], "null_rate_shifts": []}

    current_cols = set(current["columns"].keys())
    baseline_cols = set(baseline["columns"].keys())

    drift["new_columns"] = list(current_cols - baseline_cols)
    drift["removed_columns"] = list(baseline_cols - current_cols)

    for col_name in current_cols & baseline_cols:
        cur, base = current["columns"][col_name], baseline["columns"][col_name]
        if cur["dtype"] != base["dtype"]:
            drift["dtype_changes"].append({"column": col_name, "was": base["dtype"], "now": cur["dtype"]})
        null_shift = abs(cur["null_rate"] - base["null_rate"])
        if null_shift > 0.05:  # flag any >5pp swing in null rate
            drift["null_rate_shifts"].append({
                "column": col_name, "was": base["null_rate"], "now": cur["null_rate"]
            })

    return drift


def generate_report(client, table_name: str, profile: dict, drift: dict | None = None) -> str:
    """Ask Claude to turn raw profile/drift stats into a plain-English report."""
    system = (
        "You are a data quality analyst. Given raw profiling stats for a table, write a "
        "concise report for a data team Slack channel: an overall severity rating "
        "(Low/Medium/High), the 2-4 most important findings, and 1-3 concrete recommended "
        "next steps. Be specific and cite actual numbers from the stats. No fluff."
    )
    user_prompt = (
        f"Table: {table_name}\n\n"
        f"Current profile:\n{json.dumps(profile, indent=2, default=str)}\n\n"
    )
    if drift:
        user_prompt += f"Drift vs. baseline:\n{json.dumps(drift, indent=2, default=str)}\n\n"
    user_prompt += "Write the report now."

    return ask_claude(client, system, user_prompt)
