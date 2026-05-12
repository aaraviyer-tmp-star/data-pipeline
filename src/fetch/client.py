"""
fetch/client.py
Fetches raw metric records from the API.

Raises
------
ApiError
    Any non-200 HTTP response.
ApiResponseError
    Response was 200 OK but the expected data field is missing or has the
    wrong type — the specific failure mode that broke the pipeline when the
    API renamed "records" → "results".
ApiEmptyResponseError
    The records list is empty or None after extraction.
"""

import requests
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from ..config import settings


class ApiError(Exception):
    """Base exception for API fetch failures."""
    pass


class ApiResponseError(ApiError):
    """
    Raised when the API returns 200 but the response shape is unexpected.
    Catches the "changed field name" failure mode explicitly.
    """
    def __init__(self, message: str, response: dict[str, Any], key: str):
        super().__init__(message)
        self.response = response
        self.key = key


class ApiEmptyResponseError(ApiError):
    """Raised when records list is empty or None after extraction."""
    def __init__(self, key: str, records: Any):
        super().__init__(
            f"API response contains no records. "
            f"Field '{key}' is {'None' if records is None else 'an empty list'}."
        )
        self.records = records
        self.key = key


@dataclass
class FetchResult:
    records: list[dict[str, Any]]
    fetched_at: datetime
    start_date: datetime
    end_date: datetime


def fetch_metrics(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> FetchResult:
    """
    Fetch metric records from the configured API endpoint.

    Parameters
    ----------
    start_date, end_date
        Date range for the query. Defaults to yesterday → today.

    Returns
    -------
    FetchResult
        Contains the raw records list and timestamps.

    Raises
    ------
    ApiError
        On HTTP-level failures.
    ApiResponseError
        When the response is 200 OK but the expected data field is absent
        or structurally wrong — catches field rename failures.
    ApiEmptyResponseError
        When the records list is empty.
    """
    if end_date is None:
        end_date = datetime.utcnow()
    if start_date is None:
        start_date = end_date - timedelta(days=1)

    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    params = {
        "start": start_date.isoformat(),
        "end": end_date.isoformat(),
        "format": "json",
    }

    response = requests.get(settings.api_url, headers=headers, params=params, timeout=30)

    if response.status_code != 200:
        raise ApiError(
            f"API returned status {response.status_code}: {response.text[:500]}"
        )

    try:
        raw: dict[str, Any] = response.json()
    except Exception as e:
        raise ApiError(f"API response was not valid JSON: {e}") from e

    _validate_response(raw)

    records_key = settings.api_records_key
    data = raw.get("data")
    if data is None:
        raise ApiResponseError(
            f"Response JSON is missing the 'data' field. Response keys: {list(raw.keys())}",
            response=raw,
            key=records_key,
        )

    records = data.get(records_key)
    if records is None:
        raise ApiResponseError(
            f"Response 'data' object is missing the '{records_key}' field. "
            f"Available fields: {list(data.keys())}",
            response=raw,
            key=records_key,
        )

    if not isinstance(records, list):
        raise ApiResponseError(
            f"Response 'data.{records_key}' is not a list (got {type(records).__name__}). "
            f"Check whether the API changed a field name.",
            response=raw,
            key=records_key,
        )

    if len(records) == 0:
        raise ApiEmptyResponseError(key=records_key, records=records)

    return FetchResult(
        records=records,
        fetched_at=datetime.utcnow(),
        start_date=start_date,
        end_date=end_date,
    )


def _validate_response(raw: dict[str, Any]) -> None:
    """Validate top-level response structure. Raise ApiError on hard failures."""
    if not isinstance(raw, dict):
        raise ApiError(f"API response root is not a JSON object (got {type(raw).__name__})")
    if "data" not in raw:
        raise ApiError(
            f"API response is missing top-level 'data' field. Keys: {list(raw.keys())}"
        )
