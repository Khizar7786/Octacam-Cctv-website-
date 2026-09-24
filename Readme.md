# OctaCam

OctaCam is a Pakistani CCTV store in development. This repository currently contains the specifications, Django backend foundation, account authentication API, and brand/category APIs. Storefront, products, checkout, survey booking, and password recovery have not been built yet.

## Run the backend locally

Requirements: Python 3.12, Docker with a running engine, and Docker Compose. From the repository root:

```powershell
py -3.12 -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
docker compose up -d db
cd backend
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py runserver
```

Open `http://127.0.0.1:8000/health/live`, `http://127.0.0.1:8000/health/ready`, `http://127.0.0.1:8000/api/schema/`, or `http://127.0.0.1:8000/api/docs/`. The database container uses host port **5433** to avoid conflicts with an existing PostgreSQL service on 5432. Its `octacam_dev` password is for local development only. Run `docker compose down` from the repository root to stop the container; the named volume keeps local data.

If you already have PostgreSQL, skip Compose and set `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, and `POSTGRES_PORT` before running Django. `DATABASE_URL` (for example, `postgresql://user:password@host:5432/database?sslmode=require`) takes precedence over those settings. Local defaults match Compose.

### This Windows workspace without Docker

This machine also has an isolated native PostgreSQL cluster in the ignored `.local-postgres/` directory. It uses the same local development credentials and port 5433 as Compose. From the repository root, restart it with:

```powershell
pg_ctl -D .local-postgres\data -l .local-postgres\postgres.log -o '-h 127.0.0.1 -p 5433' start
cd backend
.venv\Scripts\python.exe manage.py runserver
```

Stop Django with Ctrl+C, then run `pg_ctl -D .local-postgres\data stop` from the repository root. Stop this native cluster before starting the Compose database, since both use port 5433. The cluster is local development data and is excluded from Git.

To run checks from `backend/` with the database running:

```powershell
$env:DJANGO_SETTINGS_MODULE = "config.settings.test"
.venv\Scripts\python.exe manage.py test
.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
Remove-Item Env:DJANGO_SETTINGS_MODULE
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py spectacular --validate --file schema.yml
Remove-Item schema.yml
```

The test suite uses PostgreSQL and needs permission to create a temporary test database. The custom email-login user table is created by `accounts.0001_initial`; do not switch to Django's default user model after migrating.

## Configuration

`manage.py` uses `config.settings.local`; WSGI and ASGI default to `config.settings.production`. Production refuses to start without `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` (comma-separated), and a PostgreSQL `DATABASE_URL`. Production sets secure cookies, HTTPS redirect, and HSTS; configure HTTPS at the reverse proxy before using it. The test settings retain PostgreSQL rather than swapping in SQLite.

## Authentication API

The API exposes `POST /api/v1/auth/register/`, `login/`, `refresh/`, and `logout/`; `GET /api/v1/auth/csrf/`; `GET /api/v1/account/profile/` for customers; and `GET /api/v1/staff/profile/` for staff. Password recovery remains for a later slice. Public registration always creates a customer account. Staff accounts must be created or granted `is_staff` through a trusted administrative process, never through registration input.

Start by requesting `GET /api/v1/auth/csrf/`. It returns `csrfToken` and sets a CSRF cookie. Send that token in `X-CSRFToken` on all four auth POST endpoints. Registration accepts `email`, `full_name`, optional `phone`, and `password`; login accepts `email` and `password`. Both return a short-lived `access` token and user details, and set a seven-day refresh token in an HttpOnly, SameSite=Lax cookie scoped to `/api/v1/auth/` (Secure in production). Keep the access token in application memory and send it as `Authorization: Bearer <token>` to profile endpoints. A page reload can call `refresh/` with the cookie and CSRF header to obtain a new access token and rotated cookie. Coordinate simultaneous refresh attempts into one request; a used refresh token cannot be used again. Logout revokes the refresh cookie and the client discards its access token. An already issued access token remains valid until its five-minute expiry unless the account is disabled or its password changes.

Login, registration, and refresh have in-process rate limits. Production needs an edge-level rate limit as well when multiple Django processes run. Run `python manage.py flushexpiredtokens` on a schedule to remove expired token records. Do not deploy this foundation to take real orders.

## Brand and category APIs

Visitors can list active brands/categories and retrieve them by slug. Staff can list all entries, create them, and edit or deactivate them by ID using a Bearer access token. Lists return 20 entries per page. See [the endpoint and Swagger walkthrough](Docs/catalog-api.md) for request examples and expected permission responses. Apply the catalog migration with `python manage.py migrate` before trying these routes.

Staff can also create and edit unpublished product drafts, including taxonomy, identifiers, descriptions, warranty text, and regular/optional sale prices. Stock, images, and publication are reserved for later workflows. See [the product draft API walkthrough](Docs/product-draft-api.md).
