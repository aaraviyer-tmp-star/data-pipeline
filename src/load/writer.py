"""
load/writer.py
Handles writing the report to disk and sending it via email.

Both operations are isolated here so they can be tested independently
of the fetch/transform stages.
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from typing import BinaryIO

from ..config import settings
from ..transform import TransformedMetrics


class EmailError(Exception):
    """Raised when the SMTP operation fails."""
    pass


def write_csv_report(metrics: TransformedMetrics, date: datetime | None = None) -> str:
    """
    Write the metrics report to a CSV file.

    Parameters
    ----------
    metrics
        Aggregated pipeline output.
    date
        Date used in the filename. Defaults to today.

    Returns
    -------
    str
        Absolute path to the written file.
    """
    if date is None:
        date = datetime.utcnow()

    os.makedirs(settings.report_dir, exist_ok=True)
    filename = f"report_{date.strftime('%Y%m%d')}.csv"
    filepath = os.path.join(settings.report_dir, filename)

    with open(filepath, "w", newline="") as f:
        f.write("NUVEXA DAILY METRICS REPORT\n")
        f.write(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
        f.write(f"Peak Hour: {metrics.peak_hour}:00\n")
        f.write(f"Total Records: {metrics.cleaned_count}\n")
        f.write("\n")

        f.write("TOP 10 USERS\n")
        if not metrics.top_users.empty:
            f.write("user,total_value\n")
            for _, row in metrics.top_users.iterrows():
                f.write(f"{row['user']},{row['total_value']}\n")
        else:
            f.write("No users\n")

        f.write("\nDAILY SUMMARY\n")
        if not metrics.daily_summary.empty:
            metrics.daily_summary.to_csv(f, index=False)
        else:
            f.write("No data\n")

    return os.path.abspath(filepath)


def send_report_email(report_path: str, date: datetime | None = None) -> None:
    """
    Send the report CSV as an attachment via SMTP.

    Parameters
    ----------
    report_path
        Absolute path to the CSV file to attach.
    date
        Date string used in the email subject. Defaults to today.

    Raises
    ------
    EmailError
        On SMTP connection, TLS, login, or send failures.
    """
    if date is None:
        date = datetime.utcnow()

    msg = MIMEMultipart()
    msg["From"] = settings.email_from
    msg["To"] = settings.email_to
    msg["Subject"] = f"Nuvexa Daily Metrics Report - {date.strftime('%Y-%m-%d')}"

    body = (
        "Please find attached the Nuvexa daily metrics report.\n\n"
        "This is an automated pipeline delivery. "
        "For issues, contact the data platform team."
    )
    msg.attach(MIMEText(body, "plain"))

    try:
        with open(report_path, "rb") as f:
            attachment: BinaryIO = f
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
    except OSError as e:
        raise EmailError(f"Could not read attachment at {report_path}: {e}") from e

    encoders.encode_base64(part)
    part.add_header(
        "Content-Disposition",
        f"attachment; filename={os.path.basename(report_path)}",
    )
    msg.attach(part)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            server.starttls()
            server.login(settings.email_from, settings.email_password)
            server.sendmail(
                settings.email_from,
                [settings.email_to],
                msg.as_string(),
            )
    except smtplib.SMTPException as e:
        raise EmailError(f"SMTP operation failed: {e}") from e
