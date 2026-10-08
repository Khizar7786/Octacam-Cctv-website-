# Trying brand and category APIs

These routes belong to the `catalog` Django app. Categories are flat. Brands and categories share taxonomy fields and access rules; brands additionally support one optional logo. No real catalog entries are seeded automatically.

## Routes

All paths below start with `/api/v1/`.

| Method | Path | Access and behavior |
| --- | --- | --- |
| GET | `catalog/brands/` | Anyone; active entries only |
| GET | `catalog/brands/{slug}/` | Anyone; inactive or missing entries return 404 |
| GET | `catalog/categories/` | Anyone; active entries only |
| GET | `catalog/categories/{slug}/` | Anyone; inactive or missing entries return 404 |
| GET, POST | `staff/catalog/brands/` | Staff; list all entries or create one, optionally uploading a logo |
| PATCH | `staff/catalog/brands/{id}/` | Staff; edit, deactivate, reactivate, upload/replace/remove a logo |
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

## Brand logos

Apply the catalog migration before using logo fields. Existing JSON brand creation/updates continue to work. Public brand list/detail and staff brand list/create/update responses now include `logo_url`, which is `null` without a logo. The value comes directly from Django's configured storage and may be a relative development media URL or an absolute object-storage/CDN URL. The raw `logo` upload and `remove_logo` inputs are write-only; categories do not gain logo fields.

In Swagger, select `multipart/form-data` for either staff brand POST or PATCH, then choose a file for `logo`. POST still requires `name` and `slug`; PATCH can contain just the logo. Uploading to a brand with a logo replaces it. Send all taxonomy fields you want to edit in the same request. PNG, JPEG, and WebP are accepted, up to **2 MB (2,097,152 bytes)**, with the existing catalog safety limits of 6000 pixels per side and 24 million pixels total. Invalid files, MIME/content mismatches, unsupported formats, and animated images return 400 with a field-associated `logo` error. Accepted files are decoded and normalized to remove embedded metadata; PNG/WebP transparency is retained. Client filenames are replaced with unique keys under `brands/`.

Remove a logo using either of these JSON PATCH bodies:

```json
{"logo": null}
```

```json
{"remove_logo": true}
```

For multipart or form-encoded PATCH, send `remove_logo=true` and omit the file. Uploading a file and requesting removal together returns 400. Omitting both inputs, or sending only `remove_logo=false`, leaves the existing logo unchanged. Removing an absent logo succeeds with `logo_url: null`. A JSON string containing a storage key or remote URL is not an upload and is rejected.

These operations use the existing staff Bearer permission checks. Public endpoints remain read-only and hide inactive brands. Replacements/removals delete the old file only after the database transaction commits; invalid requests and rollbacks preserve the currently referenced file. Local development serves these files through the existing DEBUG-only `/media/` route. Production continues to use the configured object-storage backend; this API does not require filesystem paths.

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
