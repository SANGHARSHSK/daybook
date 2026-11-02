# Daybook

Daybook is a small personal finance ledger built for a handful of people who want a clear picture of where their money goes. Import a bank CSV, review the rows, then explore monthly spending, categories, and individual transactions. It is a Django rebuild of an earlier Flask prototype.

## What it does

- Separate accounts and transaction records for each user.
- Reviewable CSV imports with row-level feedback before saving.
- Duplicate detection across repeated imports.
- Monthly spending and income totals, a six-month spending view, and a clearly labeled three-month spending average.
- Internal and credit-card payments can be kept as transfers so they do not inflate spending totals.
- Search and filters for transaction history, plus a CSV export.
- Responsive pages with server-rendered Django templates; no JavaScript framework or third-party analytics.

The estimate is a simple average of the last three complete months with recorded activity. It is a planning aid, not a claim about future spending.

## Run locally

Requires Python 3.12 or newer.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. The local database is SQLite. The optional `REGISTRATION_INVITE_CODE` environment variable restricts signups to people who know that code. Set it for a small shared deployment.

The earlier Flask source files are kept under `legacy_flask/` as a reference; Django is the active app.

For a Unix-like shell, activate with `source .venv/bin/activate` and export environment variables with `export NAME=value`.

## CSV format

Required columns are a date, description, and amount. Common bank header names are recognized automatically. Type, category, and account are optional. Dates such as `01/15/2025`, `15/01/2025`, and `2025-01-15` are supported. If the file has no type column, negative amounts are treated as expenses and positive amounts as income. The import review shows valid rows and skips malformed rows with an explanation.

Each import is staged in the database until it is confirmed or discarded. The original uploaded file is not retained. Repeated imports are checked against a per-user fingerprint built from the transaction details.

## Deploy on Render

The app is prepared for Render’s Django + PostgreSQL deployment flow. Create a PostgreSQL database and a Python web service connected to this repository, then configure:

- **Build command:** `bash build.sh`
- **Start command:** `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`
- **Environment:** `DATABASE_URL` (the database’s internal URL), `DJANGO_SECRET_KEY` (generate a unique secret), `DJANGO_DEBUG=false`, and `REGISTRATION_INVITE_CODE` (a private invite value for the small user group).

The service reads the hosted hostname from `RENDER_EXTERNAL_HOSTNAME`. Add any custom domain to `DJANGO_ALLOWED_HOSTS`. After deployment, create the first admin account from the provider’s shell with `python manage.py createsuperuser`. Check `/health/` for a simple health response.

For a portfolio walkthrough, create a separate reviewer account and run `python manage.py seed_demo_data reviewer`. The command adds fictional recent activity only to an empty account; it does not touch anyone else’s ledger.

Render’s current Django guide describes the PostgreSQL URL, static file serving, build command, and service start command: [Deploy a Django App on Render](https://render.com/docs/deploy-django). Review the provider’s current plan, database persistence, and pricing before creating hosted resources.

## Data and security notes

- Production mode requires a private `DJANGO_SECRET_KEY`, disables debug, redirects to HTTPS, and marks session and CSRF cookies secure.
- Database queries in the user-facing views are scoped to the signed-in user.
- The CSV upload size is capped at 8 MB. Exported text is guarded against spreadsheet formula interpretation.
- Configure regular encrypted database backups with the hosting provider before relying on the service for long-term records.
- This project does not connect to banks or store payment card numbers or bank credentials.

## Project layout

```text
config/                 Django settings and entry points
ledger/                 accounts, transactions, imports, and summaries
ledger/services/        CSV normalization and dashboard calculations
ledger/templates/       server-rendered pages
static/ledger/          responsive visual system
```
