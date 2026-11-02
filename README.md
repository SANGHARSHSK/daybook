# Daybook

Daybook is a Django app for importing bank CSVs and reviewing personal spending. Each account has its own transactions. It runs on SQLite for local development and can use PostgreSQL through `DATABASE_URL` when deployed.

## Why I built this

The first version was a small Flask script that summarized a transaction CSV. I rebuilt it with Django to add user accounts, a review step for imports, and a deployment setup I could maintain and explain as a portfolio project.

## Features

- Sign up and sign in with Django authentication. Production signups require an invite code.
- Import CSV transactions, inspect valid and invalid rows, then confirm or discard the import.
- Skip transactions already imported for the same user. Identical repeated rows within one statement are kept.
- Classify entries as expenses, income, or transfers. Credit card payment categories are treated as transfers in spending totals.
- View current-month totals, category totals, six months of spending, and a simple average of the previous three complete months.
- Search and filter transactions by description, type, category, and month. Export the signed-in user's transactions to CSV.
- Load fictional recent transactions into an empty reviewer account with a Django management command.

The three-month figure is an average of recorded expense totals. It is not a trained forecasting model.

## Technologies used

- Python 3.12 or newer
- Django 6.1
- SQLite locally; PostgreSQL with `psycopg` when `DATABASE_URL` is set
- `dj-database-url` and `python-dotenv` for configuration
- WhiteNoise and Gunicorn for deployment
- Django templates, CSS, and a small amount of browser JavaScript

## Project structure

```text
.
├── config/                         # Django settings, URL config, WSGI and ASGI
├── ledger/
│   ├── management/commands/         # seed_demo_data command
│   ├── migrations/                 # database schema
│   ├── services/                   # CSV parsing and spending summaries
│   ├── templates/                  # login, import, dashboard and transaction pages
│   ├── tests.py                    # import and user-isolation tests
│   ├── models.py                   # imports and transactions
│   ├── forms.py
│   ├── urls.py
│   └── views.py
├── static/ledger/                  # CSS and file-picker behavior
├── .env.example
├── build.sh                        # install, collect static files, run migrations
├── manage.py
├── Procfile
└── requirements.txt
```

## How it works

The user uploads a CSV through the import form. `ledger/services/imports.py` recognizes common header names, parses dates and amounts, and reports rows it cannot read. Valid rows are stored as staged transactions so the user can review a sample before confirming. The uploaded file itself is not saved as a media file.

On confirmation, the app moves staged rows into the user's transaction ledger. A fingerprint based on transaction details is used to recognize repeat imports; an occurrence number keeps identical purchases in the same file distinct. Each dashboard, list, import review, and export query is scoped to the signed-in user.

The dashboard totals are calculated with Django ORM queries. Transfers are omitted from expense totals. The “next month guide” is the arithmetic mean of the three previous complete months when each month has recorded expense data.

### CSV input

The required columns are date, description, and amount. Type, category, and account are optional; common names such as `Transaction Type` and `Account Name` are recognized. Dates in `MM/DD/YYYY`, `DD/MM/YYYY`, and `YYYY-MM-DD` forms are accepted. When a type column is missing, negative amounts are expenses and positive amounts are income. Ambiguous slash dates are read month-first.

Uploads are limited to 8 MB and 25,000 rows. Invalid rows are reported and left out of the import.

## Installation and setup

Clone the repository and create a virtual environment:

```powershell
git clone https://github.com/SANGHARSHSK/daybook.git
cd daybook
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

On macOS or Linux, use these venv commands instead:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

The example environment file enables local debug mode and uses SQLite. The `.env` file is ignored by Git. Change its placeholder secret before using the app outside local development.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `DJANGO_SECRET_KEY` | Django signing key. A local fallback is used only in debug mode; a key must be set when debug is off. |
| `DJANGO_DEBUG` | Set to `true` locally. Use `false` for deployment. |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames. Defaults to `localhost,127.0.0.1`. |
| `DATABASE_URL` | Optional locally. Without it, debug mode uses `db.sqlite3`; production requires a database URL. |
| `REGISTRATION_INVITE_CODE` | Optional in debug mode and required when debug is off. Signups must provide this value. |
| `SECURE_SSL_REDIRECT` | In production, defaults to `true`. Set only when the hosting setup handles HTTPS redirects separately. |
| `RENDER_EXTERNAL_HOSTNAME` | Added to allowed hosts automatically when provided by Render. |

Do not commit `.env` or put real credentials in `.env.example`.

## Database setup and running locally

Apply Django's migrations, then start the development server:

```bash
python manage.py migrate
python manage.py runserver
```

Open <http://127.0.0.1:8000/> and create an account through the signup page. To create an admin account for `/admin/`, run:

```bash
python manage.py createsuperuser
```

For PostgreSQL, install the listed dependencies and set `DATABASE_URL`. In production, debug must be off, `DJANGO_SECRET_KEY` and `REGISTRATION_INVITE_CODE` must be set, and migrations are run by `build.sh`.

Run the automated tests with:

```bash
python manage.py test
```

## Deployment

The repository includes a Render-oriented build script and `Procfile`. Configure a Python web service with:

- Build command: `bash build.sh`
- Start command: `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`
- Environment variables: `DATABASE_URL`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false`, and `REGISTRATION_INVITE_CODE`

Set `DJANGO_ALLOWED_HOSTS` for any custom domain. Render supplies `RENDER_EXTERNAL_HOSTNAME` for the service hostname. Review Render's [Django deployment guide](https://render.com/docs/deploy-django) and Django's [deployment checklist](https://docs.djangoproject.com/en/6.1/howto/deployment/checklist/) before deploying.

To prepare a fictional reviewer ledger, first create an account named `reviewer`, then run:

```bash
python manage.py seed_demo_data reviewer
```

The command only adds sample data if that account has no transactions.

## Routes

There is no REST API. The app has these main page routes:

| Route | Purpose |
| --- | --- |
| `/` | Spending dashboard; requires sign-in |
| `/accounts/login/` | Sign in |
| `/accounts/signup/` | Create an account |
| `/transactions/` | Search and filter transactions |
| `/transactions/export/` | Download the current user's transactions as CSV |
| `/imports/new/` | Upload a CSV |
| `/admin/` | Django admin; requires a staff account |
| `/health/` | Public plain-text health response (`ok`) |

Import review, confirmation, cancellation, and the Django admin have their own routes.

## Current limitations

- Transactions are added through CSV import or Django admin; there is no user-facing manual entry, edit, or delete form.
- If a CSV omits the transaction type, negative amounts are treated as expenses and positive amounts as income. Check this assumption against the bank's export format.
- Category and account names are kept as text from the import. There is no category management or budgeting workflow.
- Amounts are displayed in rupees. Multi-currency conversion is not implemented.
- The three-month average needs expense data in each of the previous three complete months. It does not estimate missing months.
- Daybook does not connect to bank accounts.

## What I learned

The import flow needed more care than the dashboard: bank CSVs use different headers and date formats, malformed rows should not block good ones, and repeated identical purchases should not disappear during deduplication. I also had to scope every user-facing transaction query to its owner and keep local settings separate from deployment secrets.

## Author

Sangharsh Kamble · [GitHub](https://github.com/SANGHARSHSK)
