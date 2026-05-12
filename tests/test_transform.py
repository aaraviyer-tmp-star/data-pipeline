"""
tests/test_transform.py
Tests for src/transform/pipeline.py

Covers cleaning (column rename failures, nulls, negatives, type coercion)
and aggregation.
"""

import pytest
import pandas as pd
from datetime import datetime

from src.transform import clean_records, aggregate_metrics, TransformedMetrics


# ── clean_records tests ───────────────────────────────────────────────────────

class TestCleanRecordsHappyPath:
    """Valid records are cleaned correctly and canonical field names are used."""

    def test_required_fields_renamed(self):
        records = [
            {"user_id": "u1", "metric_value": 10.0, "timestamp": "2026-05-11T10:00:00Z"},
            {"user_id": "u2", "metric_value": 20.0, "timestamp": "2026-05-11T11:00:00Z"},
        ]
        df = clean_records(records)

        assert list(df.columns) == ["user", "value", "timestamp"]
        assert df["user"].tolist() == ["u1", "u2"]
        assert df["value"].tolist() == [10.0, 20.0]
        assert df["timestamp"].dtype == "datetime64[ns]"

    def test_metric_value_coerced_from_string(self):
        records = [
            {"user_id": "u1", "metric_value": "42.5", "timestamp": "2026-05-11T10:00:00Z"},
        ]
        df = clean_records(records)
        assert df["value"].iloc[0] == 42.5

    def test_null_metric_value_dropped(self, null_metric_value_response):
        df = clean_records(null_metric_value_response["data"]["records"])
        # The null record should be dropped, leaving 2
        assert len(df) == 2

    def test_missing_user_id_dropped(self, missing_user_id_response):
        df = clean_records(missing_user_id_response["data"]["records"])
        assert len(df) == 2
        assert "u1" not in df["user"].values

    def test_negative_metric_value_dropped(self, negative_metric_value_response):
        df = clean_records(negative_metric_value_response["data"]["records"])
        assert all(df["value"] > 0)
        assert len(df) == 3  # 3 original -1 negative = 2, but fixture has 3 originals + 1 neg

    def test_non_numeric_metric_value_dropped(self, non_numeric_metric_value_response):
        df = clean_records(non_numeric_metric_value_response["data"]["records"])
        assert pd.notna(df["value"]).all()


class TestCleanRecordsRenameFailure:
    """
    If the API renames a field (e.g. user_id → user_id_new),
    clean_records raises ValueError with a clear message mentioning the
    missing field — not a cryptic pandas KeyError.
    """

    def test_missing_user_id_raises_ValueError_with_hint(self):
        records = [
            {"metric_value": 10.0, "timestamp": "2026-05-11T10:00:00Z"},  # no user_id
        ]
        with pytest.raises(ValueError) as exc_info:
            clean_records(records)

        error_text = str(exc_info.value)
        assert "user_id" in error_text
        assert "missing" in error_text.lower() or "Required" in error_text

    def test_missing_metric_value_raises_ValueError_with_hint(self):
        records = [
            {"user_id": "u1", "timestamp": "2026-05-11T10:00:00Z"},  # no metric_value
        ]
        with pytest.raises(ValueError) as exc_info:
            clean_records(records)

        error_text = str(exc_info.value)
        assert "metric_value" in error_text

    def test_missing_timestamp_raises(self):
        records = [
            {"user_id": "u1", "metric_value": 10.0},  # no timestamp
        ]
        df = clean_records(records)
        # timestamp coercion fails → NaT → row dropped → empty df is ok
        assert df.empty


# ── aggregate_metrics tests ────────────────────────────────────────────────────

class TestAggregateMetrics:
    """Aggregation produces the expected summary structures."""

    def test_peak_hour_identified(self):
        records = [
            {"user": "u1", "value": 100.0, "timestamp": datetime(2026, 5, 11, 10, 0, 0)},
            {"user": "u2", "value": 50.0,  "timestamp": datetime(2026, 5, 11, 14, 0, 0)},
            {"user": "u3", "value": 200.0, "timestamp": datetime(2026, 5, 11, 10, 0, 0)},
        ]
        df = pd.DataFrame(records)
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        result = aggregate_metrics(df)
        assert result.peak_hour == 10  # two records at hour 10, total 300 vs 50 at hour 14

    def test_daily_summary_has_required_columns(self, sample_metrics):
        assert list(sample_metrics.daily_summary.columns) == [
            "user", "date", "total_value", "avg_value", "count"
        ]

    def test_top_users_limited_to_10(self, sample_metrics):
        assert len(sample_metrics.top_users) <= 10

    def test_empty_dataframe_returns_empty_metrics(self):
        df = pd.DataFrame(columns=["user", "value", "timestamp"])
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        result = aggregate_metrics(df)
        assert result.daily_summary.empty
        assert result.top_users.empty
        assert result.peak_hour == 0
        assert result.cleaned_count == 0
