# OctaCam

OctaCam is a Pakistani CCTV store in development. This repository currently contains the specifications and the initial Django backend foundation. Storefront, catalog, checkout, survey booking, and authentication endpoints have not been built yet.

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

The backend has no customer or staff authentication endpoints yet. DRF's default permission is authenticated-only and no authentication mechanism is enabled until that slice is implemented. Do not deploy this foundation to take real orders.
