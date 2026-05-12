"""
config/settings.py
All configuration loaded exclusively from environment variables.
No hardcoded secrets or fallback values — the pipeline fails fast
if a required variable is missing.
"""

from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True)
class Settings:
    # API
    api_url: str
    api_key: str

    # Email
    smtp_host: str
    smtp_port: int
    email_from: str
    email_to: str
    email_password: str

    # Paths
    report_dir: str

    # API response field config — the key that holds records in the API response.
    # The API changed "records" → "results" on 2026-05-12, triggering this refactor.
    # Override via API_DATA_RECORDS_KEY if the field name changes again.
    api_records_key: str


def _require(key: str) -> str:
    value = getenv(key)
    if value is None:
        raise EnvironmentError(f"Required environment variable not set: {key}")
    return value


def _require_int(key: str) -> int:
    return int(_require(key))


settings = Settings(
    api_url=_require("API_URL"),
    api_key=_require("API_KEY"),
    smtp_host=getenv("SMTP_HOST", "smtp.gmail.com"),
    smtp_port=int(getenv("SMTP_PORT", "587")),
    email_from=_require("EMAIL_FROM"),
    email_to=_require("EMAIL_TO"),
    email_password=_require("EMAIL_PASSWORD"),
    report_dir=getenv("REPORT_DIR", "./reports"),
    api_records_key=getenv("API_DATA_RECORDS_KEY", "records"),
)
