# Trying the product draft API

The product draft endpoints let staff prepare catalog information and prices. They do not publish products, upload images, or adjust stock.

## Routes

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/api/v1/staff/catalog/products/` | List every product draft, 20 per page |
| POST | `/api/v1/staff/catalog/products/` | Create an unpublished, zero-stock draft |
| GET | `/api/v1/staff/catalog/products/{id}/` | Retrieve one draft |
| PATCH | `/api/v1/staff/catalog/products/{id}/` | Edit supplied fields and record price changes |

All four routes require a valid staff Bearer access token. Visitors receive 401 and customers receive 403. DELETE is unavailable. There is no public product endpoint in this slice, so drafts cannot appear to visitors.

## Supported information

A draft accepts brand and category IDs, SKU, slug, name, short and full descriptions, regular price, optional sale price, and warranty text. The response also includes the derived selling price, stock quantity, publication status, and timestamps.

The server trims and uppercases SKU values, lowercases slugs, and enforces case-insensitive uniqueness for both. Regular price must be zero or greater. Sale price may be `null`; when supplied, it must be zero or greater and strictly lower than regular price. Prices accept at most two decimal places and up to ten digits before the decimal point. The selling price is the sale price when present and the regular price otherwise.

Every new draft has `is_published: false` and `stock_quantity: 0`. Supplying either field on create or edit returns a validation error so the caller does not mistakenly believe publication or inventory changed.

When an edit changes either price field, the server records one `PRODUCT_PRICE_CHANGED` audit event with the staff user, product ID, time, and before/after price values. The product update and history record commit together.

## Try it in Swagger

1. Run `python manage.py migrate` from `backend`, then start Django with `python manage.py runserver`.
2. Open `http://127.0.0.1:8000/api/docs/`.
3. Use `GET /api/v1/auth/csrf/`, then log in through `POST /api/v1/auth/login/` with a staff account and the returned CSRF token. Copy the access token.
4. Select **Authorize** in Swagger and enter the access token in the Bearer field.
5. Create active brand and category entries first, or use their IDs from the staff taxonomy lists.
6. Execute `POST /api/v1/staff/catalog/products/` with those IDs and a local example such as:

```json
{
  "brand": 1,
  "category": 1,
  "sku": "DEMO-CAM-001",
  "slug": "demo-camera-001",
  "name": "Demo Camera Draft",
  "short_description": "A local product draft for API testing.",
  "full_description": "Replace this with accurate, approved product information before publication is implemented.",
  "regular_price": "12500.00",
  "sale_price": "11999.00",
  "warranty_text": "Local test wording only."
}
```

The response is 201. Keep its `id` for detail and edit requests. Use unique demo identifiers if you repeat the request.

7. Execute `PATCH /api/v1/staff/catalog/products/{id}/` to change only selected fields:

```json
{
  "regular_price": "12000.00",
  "sale_price": null
}
```

The response is 200, `selling_price` becomes `12000.00`, and one internal price-change audit event is recorded. Audit retrieval will be exposed in its later staff-audit slice.

Run the focused PostgreSQL tests from `backend` with:

```powershell
python manage.py test apps.catalog.tests.test_product_draft_api --settings=config.settings.test
```
