"""
run_pipeline.py
Top-level script: wires fetch → transform → load together.

Exit codes
----------
0  — success
1  — fetch error (API unreachable, non-200, bad response shape)
2  — transform error (cleaning/aggregation failed)
3  — load error (file write or email send failed)
"""

import sys
import traceback
from datetime import datetime

from src.config import settings
from src.fetch import fetch_metrics, ApiError
from src.transform import clean_records, aggregate_metrics
from src.load import write_csv_report, send_report_email, EmailError


def run() -> int:
    print(f"[{utcnow()}] Starting pipeline...", flush=True)

    try:
        # ── fetch ──────────────────────────────────────────────────────────────
        print(f"[{utcnow()}] Fetching metrics...", flush=True)
        fetch_result = fetch_metrics()
        print(
            f"[{utcnow()}] Fetched {len(fetch_result.records)} raw records", flush=True
        )

        # ── transform ──────────────────────────────────────────────────────────
        print(f"[{utcnow()}] Cleaning records...", flush=True)
        df = clean_records(fetch_result.records)
        print(f"[{utcnow()}] {len(df)} clean records after filtering", flush=True)

        print(f"[{utcnow()}] Aggregating metrics...", flush=True)
        metrics = aggregate_metrics(df)
        print(
            f"[{utcnow()}] Peak hour: {metrics.peak_hour}:00, "
            f"top users: {len(metrics.top_users)}",
            flush=True,
        )

        # ── load ───────────────────────────────────────────────────────────────
        print(f"[{utcnow()}] Writing CSV report...", flush=True)
        report_path = write_csv_report(metrics, fetch_result.end_date)
        print(f"[{utcnow()}] Report written to {report_path}", flush=True)

        print(f"[{utcnow()}] Sending email...", flush=True)
        send_report_email(report_path, fetch_result.end_date)
        print(f"[{utcnow()}] Email sent to {settings.email_to}", flush=True)

    except ApiError as e:
        print(f"[{utcnow()}] [FATAL] API error: {e}", flush=True)
        traceback.print_exc()
        return 1

    except (ValueError, TypeError) as e:
        print(f"[{utcnow()}] [FATAL] Transform error: {e}", flush=True)
        traceback.print_exc()
        return 2

    except EmailError as e:
        print(f"[{utcnow()}] [FATAL] Email/save error: {e}", flush=True)
        traceback.print_exc()
        return 3

    print(f"[{utcnow()}] Pipeline complete.", flush=True)
    return 0


def utcnow() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")


if __name__ == "__main__":
    sys.exit(run())
