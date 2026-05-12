"""
tests/test_fetch.py
Tests for src/fetch/client.py

The primary test case is the field-rename failure: when the API changed
"records" → "results" the old pipeline silently produced an empty report.
These tests ensure that:
1. A 200 OK with the wrong field name raises ApiResponseError (not silently fails)
2. An empty records list raises ApiEmptyResponseError (not silently passes)
3. HTTP-level errors raise ApiError with the status code
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from src.fetch import (
    fetch_metrics,
    ApiError,
    ApiResponseError,
    ApiEmptyResponseError,
)
from tests.conftest import FakeResponse


class TestFetchMetricsFieldRenameFailure:
    """
    Test the exact failure mode from 2026-05-12:
    API changed "records" → "results" and the old pipeline silently
    produced an empty report instead of raising an error.
    """

    def test_wrong_field_name_raises_ApiResponseError(
        self, renamed_field_api_response, monkeypatch
    ):
        """
        When the configured records key ('records') is absent from the
        response but a different sibling key exists ('results'), we should
        raise ApiResponseError — NOT silently return an empty result.
        """
        # Monkeypatch settings so the expected key is "records"
        # while the API actually sends "results"
        import src.fetch.client as fc
        monkeypatch.setattr(fc.settings, "api_records_key", "records")

        fake_resp = FakeResponse(renamed_field_api_response, status_code=200)

        with patch("requests.get", return_value=fake_resp):
            with pytest.raises(ApiResponseError) as exc_info:
                fetch_metrics()

        exc = exc_info.value
        assert exc.key == "records"
        assert "results" in str(exc)  # error message should mention the actual field found

    def test_wrong_field_name_mentions_available_fields_in_error(
        self, renamed_field_api_response, monkeypatch
    ):
        """The error message should list the fields that ARE present so debugging is fast."""
        import src.fetch.client as fc
        monkeypatch.setattr(fc.settings, "api_records_key", "records")

        fake_resp = FakeResponse(renamed_field_api_response, status_code=200)

        with patch("requests.get", return_value=fake_resp):
            with pytest.raises(ApiResponseError) as exc_info:
                fetch_metrics()

        error_text = str(exc_info.value)
        assert "results" in error_text  # actual field present in data
        assert "records" in error_text  # expected field mentioned

    def test_wrong_field_type_raises_ApiResponseError(self, monkeypatch):
        """
        If 'data.records' exists but is not a list (e.g. the API returns a dict),
        raise ApiResponseError with a clear message.
        """
        import src.fetch.client as fc
        monkeypatch.setattr(fc.settings, "api_records_key", "records")

        response = {"data": {"records": {"foo": "bar"}}}  # dict instead of list
        fake_resp = FakeResponse(response, status_code=200)

        with patch("requests.get", return_value=fake_resp):
            with pytest.raises(ApiResponseError) as exc_info:
                fetch_metrics()

        assert "not a list" in str(exc_info.value)


class TestFetchMetricsMissingDataField:
    """The 'data' top-level field is absent — distinct error from wrong records key."""

    def test_missing_data_field_raises_ApiResponseError(
        self, missing_data_field_api_response, monkeypatch
    ):
        import src.fetch.client as fc
        monkeypatch.setattr(fc.settings, "api_records_key", "records")

        fake_resp = FakeResponse(missing_data_field_api_response, status_code=200)

        with patch("requests.get", return_value=fake_resp):
            with pytest.raises(ApiError) as exc_info:
                fetch_metrics()

        assert "data" in str(exc_info.value)


class TestFetchMetricsEmptyRecords:
    """An empty records list should raise ApiEmptyResponseError, not pass silently."""

    def test_empty_records_list_raises_ApiEmptyResponseError(
        self, empty_records_api_response, monkeypatch
    ):
        import src.fetch.client as fc
        monkeypatch.setattr(fc.settings, "api_records_key", "records")

        fake_resp = FakeResponse(empty_records_api_response, status_code=200)

        with patch("requests.get", return_value=fake_resp):
            with pytest.raises(ApiEmptyResponseError) as exc_info:
                fetch_metrics()

        exc = exc_info.value
        assert exc.key == "records"

    def test_none_records_raises_ApiEmptyResponseError(self, monkeypatch):
        import src.fetch.client as fc
        monkeypatch.setattr(fc.settings, "api_records_key", "records")

        response = {"data": {"records": None}}
        fake_resp = FakeResponse(response, status_code=200)

        with patch("requests.get", return_value=fake_resp):
            with pytest.raises(ApiEmptyResponseError):
                fetch_metrics()


class TestFetchMetricsSuccess:
    """Happy path — valid response returns a FetchResult with the records."""

    def test_valid_response_returns_records(self, valid_api_response, monkeypatch):
        import src.fetch.client as fc
        monkeypatch.setattr(fc.settings, "api_records_key", "records")

        fake_resp = FakeResponse(valid_api_response, status_code=200)

        with patch("requests.get", return_value=fake_resp) as mock_get:
            result = fetch_metrics()

        assert len(result.records) == 3
        assert result.records[0]["user_id"] == "u1"
        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["timeout"] == 30

    def test_custom_date_range_is_passed_to_api(
        self, valid_api_response, monkeypatch
    ):
        import src.fetch.client as fc
        monkeypatch.setattr(fc.settings, "api_records_key", "records")

        fake_resp = FakeResponse(valid_api_response, status_code=200)
        start = datetime(2026, 5, 10, 0, 0, 0)
        end = datetime(2026, 5, 11, 0, 0, 0)

        with patch("requests.get", return_value=fake_resp) as mock_get:
            fetch_metrics(start_date=start, end_date=end)

        _, kwargs = mock_get.call_args
        assert "start=2026-05-10" in kwargs["params"]["start"]
        assert "end=2026-05-11" in kwargs["params"]["end"]


class TestFetchMetricsHttpErrors:
    """Non-200 responses raise ApiError with the status code."""

    @pytest.mark.parametrize("status_code,body", [
        (400, '{"error": "bad request"}'),
        (401, '{"error": "unauthorized"}'),
        (403, '{"error": "forbidden"}'),
        (429, '{"error": "rate limited"}'),
        (500, '{"error": "internal server error"}'),
    ])
    def test_http_error_raises_ApiError_with_status_code(
        self, status_code, body, monkeypatch
    ):
        import src.fetch.client as fc
        monkeypatch.setattr(fc.settings, "api_records_key", "records")

        fake_resp = MagicMock()
        fake_resp.status_code = status_code
        fake_resp.text = body

        with patch("requests.get", return_value=fake_resp):
            with pytest.raises(ApiError) as exc_info:
                fetch_metrics()

        assert str(status_code) in str(exc_info.value)

    def test_invalid_json_raises_ApiError(self, monkeypatch):
        import src.fetch.client as fc
        monkeypatch.setattr(fc.settings, "api_records_key", "records")

        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.side_effect = ValueError("not JSON")

        with patch("requests.get", return_value=fake_resp):
            with pytest.raises(ApiError) as exc_info:
                fetch_metrics()

        assert "not valid JSON" in str(exc_info.value)
