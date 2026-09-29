# OctaCam

OctaCam is a Pakistani CCTV store in development. This repository currently contains the specifications, Django backend foundation, account authentication and password reset APIs, customer profile editing and order history, catalog taxonomy, typed product specifications, staff product image management, publication controls, staff stock adjustments, public product APIs, equipment-only COD checkout, and a transactional email outbox worker. The storefront UI, order fulfillment, and survey booking have not been built yet.

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

`manage.py` uses `config.settings.local`; WSGI and ASGI default to `config.settings.production`. Production refuses to start without `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` (comma-separated), a PostgreSQL `DATABASE_URL`, `DJANGO_MEDIA_STORAGE_BACKEND` pointing to configured object storage, an HTTPS `PUBLIC_SITE_URL`, a delivery `EMAIL_BACKEND`, and `DEFAULT_FROM_EMAIL`. No production media or email provider has been selected yet. Production sets secure cookies, HTTPS redirect, and HSTS; configure HTTPS at the reverse proxy before using it. The test settings retain PostgreSQL rather than swapping in SQLite.

COD checkout also requires explicit `CHECKOUT_SHIPPING_FEE` (PKR with two decimal places), `CHECKOUT_TAX_RATE_PERCENT` (approved percentage with two decimal places), and `CHECKOUT_SHIPPING_TAXABLE` (`true` or `false`). No values are provided by the repository; quote and placement return `503 CHECKOUT_NOT_CONFIGURED` until these business inputs are approved and set. The current pricing adapter supports one percentage on product line subtotals and, if configured, shipping. Confirm that this matches the approved tax treatment before accepting real orders.

## Authentication API

The API exposes `POST /api/v1/auth/register/`, `login/`, `refresh/`, and `logout/`; password reset request and confirm routes; `GET /api/v1/auth/csrf/`; `GET /api/v1/account/profile/` for customers; and `GET /api/v1/staff/profile/` for staff. Public registration always creates a customer account. Staff accounts must be created or granted `is_staff` through a trusted administrative process, never through registration input.

Start by requesting `GET /api/v1/auth/csrf/`. It returns `csrfToken` and sets a CSRF cookie. Send that token in `X-CSRFToken` on auth POST endpoints, including both password reset routes. Registration accepts `email`, `full_name`, optional `phone`, and `password`; login accepts `email` and `password`. Both return a short-lived `access` token and user details, and set a seven-day refresh token in an HttpOnly, SameSite=Lax cookie scoped to `/api/v1/auth/` (Secure in production). Keep the access token in application memory and send it as `Authorization: Bearer <token>` to profile endpoints. A page reload can call `refresh/` with the cookie and CSRF header to obtain a new access token and rotated cookie. Coordinate simultaneous refresh attempts into one request; a used refresh token cannot be used again. Logout revokes the refresh cookie and the client discards its access token. An already issued access token remains valid until its five-minute expiry unless the account is disabled or its password changes.

Login, registration, refresh, and password reset have in-process rate limits. Production needs an edge-level rate limit as well when multiple Django processes run. Run `python manage.py flushexpiredtokens` on a schedule to remove expired token records. Do not deploy this foundation to take real orders.

### Customer account API

The existing `/api/v1/account/profile/` route supports GET and PATCH. PATCH permits `full_name` and `phone` only; email, passwords, roles, and account state cannot be edited here. `GET /api/v1/account/orders/` provides paginated history, and `GET /api/v1/account/orders/{public_id}/` returns an owned order's saved details, amounts, COD status, and courier information. All these routes require a customer Bearer access token. Staff use their separate staff routes. Matching checkout email addresses do not grant access to guest or other customers' orders, and profile updates never rewrite order snapshots. See [the customer account API walkthrough](Docs/account-api.md).

### Password recovery and email worker

With PostgreSQL running, apply migrations using `backend\.venv\Scripts\python.exe backend\manage.py migrate` from the repository root. Keep the Django server running, then open a second PowerShell terminal and run:

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py process_email_outbox
```

The worker polls every five seconds. Use `process_email_outbox --once` to process one batch and exit, or `--poll-seconds 10` to change the interval. Local email is written to the worker terminal by Django's console backend; it is not sent externally. Stop the worker with Ctrl+C. The outbox is in PostgreSQL, so a queued event survives a server or worker restart.

Placed COD orders now queue an `ORDER_PLACED` event in the same database transaction. The worker sends an order confirmation using saved item and amount snapshots. Guest emails include a signed link to the limited order tracking API. An email delivery failure leaves the placed order intact and is retried by the worker.

Request a reset through `POST /api/v1/auth/password-reset/request/` with `{"email":"you@example.com"}` and the `X-CSRFToken` from `GET /api/v1/auth/csrf/`. The response is always the same for valid, unknown, or inactive accounts. For an active account, copy `uid` and `token` from the link printed by the worker and send them with `new_password` to `POST /api/v1/auth/password-reset/confirm/`, also with the CSRF header. The link points to the future `/reset-password` storefront page; that page is not implemented yet. Tokens expire after one hour and become invalid after a successful password change.

Staff can inspect `GET /api/v1/staff/communications/emails/?status=failed` and request an immediate retry with `POST /api/v1/staff/communications/emails/{id}/retry/`. Both require a staff Bearer token. Automatic retries use increasing delays and stop after five failed attempts. An expired or invalid password reset request needs a fresh customer request instead of staff retry. The staff list exposes delivery state, attempt count, and a safe failure class without returning template context or reset links. Production must set an HTTPS `PUBLIC_SITE_URL`, `DEFAULT_FROM_EMAIL`, and a real `EMAIL_BACKEND` with its provider settings, such as Django SMTP `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, and `EMAIL_HOST_PASSWORD`. Delivery credentials are environment variables, never committed.

## Catalog APIs

Visitors can list active brands/categories and retrieve them by slug. Staff can list all entries, create them, and edit or deactivate them by ID using a Bearer access token. Lists return 20 entries per page. See [the endpoint and Swagger walkthrough](Docs/catalog-api.md) for request examples and expected permission responses. Apply the catalog migration with `python manage.py migrate` before trying these routes.

Staff can create product drafts, configure typed specifications per category, assign specification values, upload and order images, publish products, and make reasoned stock adjustments with a movement history. Visitors can search, filter, sort, list, and retrieve published products with image metadata; published products remain visible at zero stock. Filter metadata is available at `/api/v1/catalog/filters/`. Local media files are stored in ignored `backend/media/` and served at `/media/` by Django only in development. See [the product catalog API walkthrough](Docs/product-draft-api.md).

## COD checkout API

`POST /api/v1/checkout/quote/` calculates a current PKR quote for product IDs, quantities, and delivery city/province. `POST /api/v1/checkout/place/` accepts the reviewed quote token, contact and delivery address, and an `Idempotency-Key` UUID. Both guest and Bearer-authenticated customers can use these routes. Send the CSRF cookie and `X-CSRFToken` header from `GET /api/v1/auth/csrf/`. Placement returns an order receipt; a repeat request with the same key and body returns the same receipt. Start `process_email_outbox` in another terminal to see the confirmation email locally. See [the checkout request walkthrough](Docs/checkout-api.md) for payloads, conflicts, and the request-to-database flow.
