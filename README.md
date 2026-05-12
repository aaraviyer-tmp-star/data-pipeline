# data-pipeline

Nuvexa daily metrics pipeline — fetch → transform → load, fully modular and tested.

## Modules

| Module | Responsibility |
|--------|---------------|
| `src/config` | All settings from environment variables |
| `src/fetch` | API calls; raises on field-rename or empty-response failures |
| `src/transform` | Cleaning and aggregation |
| `src/load` | CSV write and email delivery |
| `src/reports` | Structured report data model |

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `API_URL` | Yes | — | Full API endpoint URL |
| `API_KEY` | Yes | — | Bearer token for the API |
| `EMAIL_FROM` | Yes | — | Sender email address |
| `EMAIL_TO` | Yes | — | Recipient email address |
| `EMAIL_PASSWORD` | Yes | — | SMTP password / app password |
| `SMTP_HOST` | No | `smtp.gmail.com` | SMTP server hostname |
| `SMTP_PORT` | No | `587` | SMTP port |
| `REPORT_DIR` | No | `./reports` | Directory for generated CSVs |
| `API_DATA_RECORDS_KEY` | No | `records` | Field name for records list in API response |

## Run

```bash
python run_pipeline.py
```

Exit codes: `0` success · `1` API error · `2` transform error · `3` load/email error

## Test

```bash
pytest -v
pytest --cov=src --cov-report=term-missing
```

## CI

GitHub Actions runs tests on every push and PR. Secrets required:

- `API_KEY`
- `EMAIL_PASSWORD`
