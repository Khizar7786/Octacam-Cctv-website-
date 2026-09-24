# Trying brand and category APIs

These routes belong to the `catalog` Django app. Categories are flat. The same fields and access rules apply to both resources. No real catalog entries are seeded automatically.

## Routes

All paths below start with `/api/v1/`.

| Method | Path | Access and behavior |
| --- | --- | --- |
| GET | `catalog/brands/` | Anyone; active entries only |
| GET | `catalog/brands/{slug}/` | Anyone; inactive or missing entries return 404 |
| GET | `catalog/categories/` | Anyone; active entries only |
| GET | `catalog/categories/{slug}/` | Anyone; inactive or missing entries return 404 |
| GET, POST | `staff/catalog/brands/` | Staff; list all entries or create one |
| PATCH | `staff/catalog/brands/{id}/` | Staff; edit, deactivate, or reactivate |
| GET, POST | `staff/catalog/categories/` | Staff; list all entries or create one |
| PATCH | `staff/catalog/categories/{id}/` | Staff; edit, deactivate, or reactivate |

Lists return `count`, `next`, `previous`, and `results`. Add `?page=2` for the next page. Page size is 20, with ordering by `sort_order`, `name`, then `id`. Public query parameters cannot reveal inactive entries. Public writes and DELETE requests are not supported.

## Try it with Swagger

1. With PostgreSQL running, open a terminal in `backend`, activate the virtual environment, and run `python manage.py migrate`.
2. If you do not have a staff account, run `python manage.py createsuperuser`. This prompts for your email, full name, and password; no admin website is required to create the account. Public registration cannot grant staff access.
3. Start Django with `python manage.py runserver`, then open `http://127.0.0.1:8000/api/docs/`. Use this same hostname throughout so browser cookies match.
4. Execute `GET /api/v1/auth/csrf/` and copy the returned `csrfToken`. The browser stores its accompanying cookie.
5. Execute `POST /api/v1/auth/login/` with your staff email and password. Paste `csrfToken` into the `X-CSRFToken` header input. Copy the returned `access` value.
6. Click Swagger's **Authorize**, paste only the access token into the Bearer authentication field, and confirm. Swagger adds the `Authorization: Bearer ...` header to staff requests. Catalog writes use this Bearer header and do not require a CSRF header. Access tokens expire after five minutes; log in again if needed.
7. Execute `POST /api/v1/staff/catalog/brands/` with this local example:

```json
{
  "name": "Example Brand",
  "slug": "example-brand",
  "description": "Local API demonstration entry.",
  "is_active": true,
  "sort_order": 0
}
```

The response is 201 with the new ID and timestamps. Only `name` and `slug` are required; description defaults to empty, active status to true, and sort order to zero. Names and slugs must be unique within their resource, including inactive entries. Slugs use letters, numbers, underscores, or hyphens. Sort order cannot be negative.

8. Open `http://127.0.0.1:8000/api/v1/catalog/brands/example-brand/` to see the public entry. Public routes work without a token.
9. Execute `PATCH /api/v1/staff/catalog/brands/{id}/`, using the returned ID, with:

```json
{
  "name": "Renamed Example Brand",
  "is_active": false
}
```

The response is 200. The row remains in the staff list, but disappears from the public list and its public detail returns 404. The slug stays `example-brand` unless explicitly edited. Send `{"is_active": true}` to reactivate it. Use a different name and slug when repeating creation rather than reusing the same example.

10. Repeat the same steps with `categories` instead of `brands`, using a name such as `Example Category` and slug `example-category`.

## Permission and validation checks

- Without a Bearer token, staff list/create/update requests return 401.
- With a customer token, those requests return 403 and do not change data.
- Staff role changes take effect for existing access tokens because permissions use the current user record.
- Duplicate names/slugs, blank required values, invalid slugs, and negative sort order return 400 in the shared `error.code/message/fields` envelope.
- Missing staff update IDs and missing/inactive public slugs return 404.

Run the PostgreSQL permission and behavior tests from `backend`:

```powershell
python manage.py test apps.catalog --settings=config.settings.test
```
