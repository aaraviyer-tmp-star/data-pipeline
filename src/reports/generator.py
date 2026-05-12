"""
reports/generator.py
Builds structured report metadata from transformed metrics.

Separating this from load.py keeps the report data model independent
of the transport layer (file vs email vs Slack, etc.).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..transform import TransformedMetrics


@dataclass
class Report:
    """Immutable report container with metadata and data."""

    date: str
    peak_hour: int
    total_records: int
    top_users: list[dict[str, Any]]
    daily_summary_rows: int
    generated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def summary_line(self) -> str:
        return (
            f"Report for {self.date}: {self.total_records} records, "
            f"peak hour {self.peak_hour}:00, "
            f"{len(self.top_users)} top users, "
            f"{self.daily_summary_rows} daily summary rows"
        )


def build_report(metrics: TransformedMetrics, date: datetime | None = None) -> Report:
    """
    Build a structured Report from aggregated metrics.

    Parameters
    ----------
    metrics
        Output from ``aggregate_metrics()``.
    date
        Date string for the report. Defaults to today (UTC).
    """
    if date is None:
        date = datetime.utcnow()

    top_users_rows = []
    if not metrics.top_users.empty:
        for _, row in metrics.top_users.iterrows():
            top_users_rows.append({
                "user": row["user"],
                "total_value": float(row["total_value"]),
            })

    return Report(
        date=date.strftime("%Y-%m-%d"),
        peak_hour=metrics.peak_hour,
        total_records=metrics.cleaned_count,
        top_users=top_users_rows,
        daily_summary_rows=len(metrics.daily_summary),
    )
