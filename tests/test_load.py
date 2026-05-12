"""
tests/test_load.py
Tests for src/load/writer.py

write_csv_report is tested against the filesystem.
send_report_email is tested with a mocked smtplib so we don't actually send email.
"""

import os
import pytest
import tempfile
from unittest.mock import patch, MagicMock
from datetime import datetime

from src.load import write_csv_report, send_report_email, EmailError


class TestWriteCsvReport:
    """CSV report is written correctly with all expected sections."""

    def test_report_file_created(self, sample_metrics, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            monkeypatch.setattr("src.config.settings", MagicMock(report_dir=tmpdir))
            # Re-import to pick up patched settings (patch settings object directly)
            from src.config.settings import Settings
            from unittest.mock import MagicMock as Mock
            mock_settings = MagicMock()
            mock_settings.report_dir = tmpdir
            with patch("src.load.writer.settings", mock_settings):
                from src.load import writer
                writer.settings.report_dir = tmpdir
                path = writer.write_csv_report(sample_metrics)

        assert os.path.exists(path)

    def test_report_contains_header(self, sample_metrics, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            from src.load import writer
            writer.settings.report_dir = tmpdir
            path = writer.write_csv_report(sample_metrics)

            with open(path) as f:
                content = f.read()

            assert "NUVEXA DAILY METRICS REPORT" in content
            assert "Peak Hour:" in content
            assert "Total Records:" in content

    def test_report_contains_top_users_section(self, sample_metrics, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            from src.load import writer
            writer.settings.report_dir = tmpdir
            path = writer.write_csv_report(sample_metrics)

            with open(path) as f:
                content = f.read()

            assert "TOP 10 USERS" in content
            assert "DAILY SUMMARY" in content

    def test_report_filename_uses_date(self, sample_metrics, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            from src.load import writer
            writer.settings.report_dir = tmpdir
            date = datetime(2026, 5, 11)
            path = writer.write_csv_report(sample_metrics, date=date)

            assert "report_20260511.csv" in path


class TestSendReportEmail:
    """SMTP operations are called correctly; no real email is sent."""

    def test_smtp_connect_called_with_settings(self, sample_metrics, monkeypatch):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            mock_settings = MagicMock()
            mock_settings.smtp_host = "smtp.gmail.com"
            mock_settings.smtp_port = 587
            mock_settings.email_from = "test@nuvexa.io"
            mock_settings.email_to = "aarav@nuvexa.io"
            mock_settings.email_password = "sekret"

            with patch("src.load.writer.settings", mock_settings):
                from src.load import writer
                writer.settings = mock_settings

                with patch("smtplib.SMTP") as mock_smtp_class:
                    mock_server = MagicMock()
                    mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_server)
                    mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

                    send_report_email(tmp_path)

                    mock_smtp_class.assert_called_once_with(
                        "smtp.gmail.com", 587, timeout=20
                    )
                    mock_server.starttls.assert_called_once()
                    mock_server.login.assert_called_once_with("test@nuvexa.io", "sekret")
                    mock_server.sendmail.assert_called_once()
        finally:
            os.unlink(tmp_path)

    def test_attachment_added_to_email(self, sample_metrics, monkeypatch):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            mock_settings = MagicMock()
            mock_settings.smtp_host = "smtp.gmail.com"
            mock_settings.smtp_port = 587
            mock_settings.email_from = "test@nuvexa.io"
            mock_settings.email_to = "aarav@nuvexa.io"
            mock_settings.email_password = "sekret"

            with patch("src.load.writer.settings", mock_settings):
                from src.load import writer
                writer.settings = mock_settings

                with patch("smtplib.SMTP") as mock_smtp_class:
                    mock_server = MagicMock()
                    mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_server)
                    mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

                    send_report_email(tmp_path)

                    # Verify sendmail was called and the message contains attachment
                    sendmail_call = mock_server.sendmail.call_args
                    msg = sendmail_call[0][2]  # third positional arg is the message string
                    assert "attachment" in msg.lower() or "octet-stream" in msg
        finally:
            os.unlink(tmp_path)

    def test_missing_attachment_file_raises_EmailError(self, monkeypatch):
        mock_settings = MagicMock()
        mock_settings.smtp_host = "smtp.gmail.com"
        mock_settings.smtp_port = 587
        mock_settings.email_from = "test@nuvexa.io"
        mock_settings.email_to = "aarav@nuvexa.io"
        mock_settings.email_password = "sekret"

        with patch("src.load.writer.settings", mock_settings):
            from src.load import writer
            writer.settings = mock_settings

            with pytest.raises(EmailError) as exc_info:
                send_report_email("/nonexistent/path/report.csv")

            assert "Could not read attachment" in str(exc_info.value)

    def test_smtp_failure_raises_EmailError(self, monkeypatch):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            mock_settings = MagicMock()
            mock_settings.smtp_host = "smtp.gmail.com"
            mock_settings.smtp_port = 587
            mock_settings.email_from = "test@nuvexa.io"
            mock_settings.email_to = "aarav@nuvexa.io"
            mock_settings.email_password = "sekret"

            with patch("src.load.writer.settings", mock_settings):
                from src.load import writer
                writer.settings = mock_settings

                import smtplib
                with patch("smtplib.SMTP") as mock_smtp_class:
                    mock_smtp_class.return_value.__enter__ = MagicMock(
                        side_effect=smtplib.SMTPException("connection refused")
                    )
                    mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

                    with pytest.raises(EmailError) as exc_info:
                        send_report_email(tmp_path)

                    assert "SMTP" in str(exc_info.value)
        finally:
            os.unlink(tmp_path)
