"""
transform/pipeline.py
Cleans raw API records and produces aggregated metrics.

Cleaning
--------
- Drops records missing required fields.
- Converts metric_value to numeric, coercing errors to NaN.
- Parses timestamp strings to datetime.
- Renames API field names to canonical internal names.

Aggregation
-----------
- Daily summary per user: sum, mean, count of values.
- Peak hour: hour with highest average metric value.
- Top-N users by total value.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd


# Canonical internal field names (after rename from API names).
# If the API changes these field names, update the rename dict in clean().
INTERNAL_COLS = {
    "metric_value": "value",
    "user_id": "user",
}


@dataclass
class TransformedMetrics:
    """Container for cleaned + aggregated pipeline output."""

    daily_summary: pd.DataFrame
    peak_hour: int
    top_users: pd.DataFrame
    raw_count: int
    cleaned_count: int
    cleaned_at: datetime = field(default_factory=datetime.utcnow)


def clean_records(records: list[dict[str, Any]]) -> pd.DataFrame:
    """
    Clean a list of raw API records into a typed DataFrame.

    Steps
    -----
    1. Drop records missing required fields (``user_id``, ``metric_value``).
    2. Coerce ``metric_value`` to numeric; coerce errors → NaN and drop.
    3. Drop rows where ``metric_value`` ≤ 0.
    4. Parse ``timestamp`` strings to datetime.
    5. Rename API field names to canonical internal names.

    Parameters
    ----------
    records
        Raw list of dicts as returned by the API.

    Returns
    -------
    pd.DataFrame
        Columns: ``user`` (str), ``value`` (float), ``timestamp`` (datetime).
        Empty DataFrame if all records are invalid.

    Raises
    ------
    ValueError
        If a required rename target column is missing from the input records
        after rename — defensive; will be caught by the field-name test.
    """
    df = pd.DataFrame(records)

    required_before_rename = list(INTERNAL_COLS.keys())
    required_after_rename = list(INTERNAL_COLS.values())

    missing_before = [c for c in required_before_rename if c not in df.columns]
    if missing_before:
        raise ValueError(
            f"Required API field(s) missing from records: {missing_before}. "
            f"Available fields: {list(df.columns)}. "
            f"Has the API renamed a field?"
        )

    df = df.dropna(subset=required_before_rename)

    df["metric_value"] = pd.to_numeric(df["metric_value"], errors="coerce")
    df = df.dropna(subset=["metric_value"])
    df = df[df["metric_value"] > 0]

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"])

    df = df.rename(columns=INTERNAL_COLS)

    missing_after = [c for c in required_after_rename if c not in df.columns]
    if missing_after:
        raise ValueError(
            f"Expected canonical column(s) missing after rename: {missing_after}. "
            f"Available columns: {list(df.columns)}."
        )

    return df.reset_index(drop=True)


def aggregate_metrics(df: pd.DataFrame) -> TransformedMetrics:
    """
    Produce summary aggregations from a cleaned DataFrame.

    Parameters
    ----------
    df
        Must contain columns: ``user`` (str), ``value`` (float), ``timestamp`` (datetime).

    Returns
    -------
    TransformedMetrics
    """
    if df.empty:
        return TransformedMetrics(
            daily_summary=pd.DataFrame(),
            peak_hour=0,
            top_users=pd.DataFrame(),
            raw_count=0,
            cleaned_count=0,
        )

    df = df.copy()
    df["date"] = df["timestamp"].dt.date
    df["hour"] = df["timestamp"].dt.hour

    daily_summary = (
        df.groupby(["user", "date"])
        .agg(total_value=("value", "sum"), avg_value=("value", "mean"), count=("value", "count"))
        .reset_index()
    )

    peak_hours = df.groupby("hour")["value"].mean().reset_index()
    peak_hours.columns = ["hour", "avg_value"]
    peak_hour = int(peak_hours.loc[peak_hours["avg_value"].idxmax(), "hour"])

    top_users = (
        daily_summary.nlargest(10, "total_value")[["user", "total_value"]].reset_index(drop=True)
    )

    return TransformedMetrics(
        daily_summary=daily_summary,
        peak_hour=peak_hour,
        top_users=top_users,
        raw_count=len(df),
        cleaned_count=len(df),
    )
