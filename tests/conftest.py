"""
tests/conftest.py
Shared pytest fixtures used across all test modules.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from src.transform import TransformedMetrics
import pandas as pd


# ── Raw API response fixtures ────────────────────────────────────────────────

@pytest.fixture
def valid_api_response():
    """Minimal valid API JSON response matching the shape the pipeline expects."""
    return {
        "data": {
            "records": [
                {
                    "user_id": "u1",
                    "metric_value": 42.5,
                    "timestamp": "2026-05-11T10:30:00Z",
                },
                {
                    "user_id": "u2",
                    "metric_value": 17.0,
                    "timestamp": "2026-05-11T14:45:00Z",
                },
                {
                    "user_id": "u1",
                    "metric_value": 8.5,
                    "timestamp": "2026-05-11T10:55:00Z",
                },
            ]
        }
    }


@pytest.fixture
def empty_records_api_response():
    """API returned 200 but the records list is empty."""
    return {"data": {"records": []}}


@pytest.fixture
def renamed_field_api_response():
    """
    API returned 200 but changed the field name from 'records' → 'results'.
    This is the exact failure that broke the pipeline this morning.
    """
    return {
        "data": {
            "results": [
                {
                    "user_id": "u1",
                    "metric_value": 42.5,
                    "timestamp": "2026-05-11T10:30:00Z",
                },
            ]
        }
    }


@pytest.fixture
def missing_data_field_api_response():
    """API returned 200 but the 'data' top-level field is absent."""
    return {"status": "ok", "something_else": []}


@pytest.fixture
def missing_user_id_response(valid_api_response):
    """Record missing the user_id field."""
    valid_api_response["data"]["records"][0].pop("user_id")
    return valid_api_response


@pytest.fixture
def null_metric_value_response(valid_api_response):
    """Record with metric_value set to null."""
    valid_api_response["data"]["records"][0]["metric_value"] = None
    return valid_api_response


@pytest.fixture
def negative_metric_value_response(valid_api_response):
    """Record with metric_value = -5 (should be dropped)."""
    valid_api_response["data"]["records"].append(
        {"user_id": "u3", "metric_value": -5.0, "timestamp": "2026-05-11T08:00:00Z"}
    )
    return valid_api_response


@pytest.fixture
def non_numeric_metric_value_response(valid_api_response):
    """Record with metric_value = 'abc' (should be coerced to NaN and dropped)."""
    valid_api_response["data"]["records"].append(
        {"user_id": "u3", "metric_value": "abc", "timestamp": "2026-05-11T08:00:00Z"}
    )
    return valid_api_response


# ── Mock requests.Response ─────────────────────────────────────────────────────

class FakeResponse:
    def __init__(self, json_data: dict, status_code: int = 200):
        self._json_data = json_data
        self.status_code = status_code
        self.text = ""

    def json(self):
        return self._json_data


# ── TransformedMetrics fixtures ───────────────────────────────────────────────

@pytest.fixture
def sample_metrics() -> TransformedMetrics:
    records = [
        {"user": "u1", "value": 42.5, "timestamp": datetime(2026, 5, 11, 10, 30, 0)},
        {"user": "u2", "value": 17.0, "timestamp": datetime(2026, 5, 11, 14, 45, 0)},
        {"user": "u1", "value": 8.5,  "timestamp": datetime(2026, 5, 11, 10, 55, 0)},
    ]
    df = pd.DataFrame(records)
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
    top_users = daily_summary.nlargest(10, "total_value")[["user", "total_value"]].reset_index(drop=True)
    return TransformedMetrics(
        daily_summary=daily_summary,
        peak_hour=peak_hour,
        top_users=top_users,
        raw_count=3,
        cleaned_count=3,
    )
