# Trying the product catalog API

The catalog API lets staff define technical attributes per category, prepare products, and publish complete records. Public endpoints expose only published products whose brand and category are active. Product images, inventory adjustments, search, and filtering remain later work.

## Routes

All paths start with `/api/v1/`.

| Method | Path | Access and behavior |
| --- | --- | --- |
| GET | `catalog/products/` | Anyone; paginated published products |
| GET | `catalog/products/{slug}/` | Anyone; one published product with displayed specifications |
| GET, POST | `staff/catalog/products/` | Staff; list products or create an unpublished draft |
| GET, PATCH | `staff/catalog/products/{id}/` | Staff; retrieve/edit, replace specifications, publish, or unpublish |
| GET, POST | `staff/catalog/categories/{id}/specifications/` | Staff; list or create definitions for one category |
| PATCH | `staff/catalog/specifications/{id}/` | Staff; edit or deactivate a definition |
| POST | `staff/catalog/specifications/{id}/choices/` | Staff; add a controlled choice |
| PATCH | `staff/catalog/specification-choices/{id}/` | Staff; edit or deactivate a choice |

Staff routes require a Bearer access token. Visitors receive 401 and signed-in customers receive 403. The API does not expose hard-delete routes for these records.

## Specification design

Each definition belongs to one category, which lets Cameras have attributes such as resolution and Storage have attributes such as capacity. Supported `data_type` values and product inputs are:

| Type | Product `value` example |
| --- | --- |
| `text` | `"1/2.8 inch CMOS"` |
| `integer` | `30` |
| `decimal` | `"2.0000"` |
| `boolean` | `true` |
| `choice` | `"4mp"`, matching an active choice's `value` |

A product specification request has this shape:

```json
{
  "definition": 1,
  "value": "4mp"
}
```

The definition must be active and belong to the product's category. Values must match its type, choice values must belong to that definition, and a definition cannot occur twice. When `specifications` is sent in a product PATCH, the array replaces the product's complete specification set. Changing category on a product that already has values therefore requires the replacement array in the same request.

Public product details include active values whose definitions have `is_displayed: true`. `is_filterable` is stored for the later filtering API but has no query behavior yet.

## Publication rules

Product creation always produces `is_published: false` with `stock_quantity: 0`. `is_published` is rejected during creation, and stock remains read-only until the inventory workflow is added.

Staff publish an existing product with:

```json
{
  "is_published": true
}
```

The brand and category must be active, core product fields must be complete, prices must be valid, and every active required specification for the category must have a valid value. A failed publication returns 400 and leaves the product as a draft. Editing a published product cannot make it incomplete. Publishing and unpublishing create `PRODUCT_PUBLISHED` and `PRODUCT_UNPUBLISHED` audit events in the same transaction.

Publication is separate from availability. A published product remains in public list and detail responses when `stock_quantity` is zero, with `is_in_stock: false`.

## Try it in Swagger

1. From `backend`, run `python manage.py migrate` and `python manage.py runserver`.
2. Open `http://127.0.0.1:8000/api/docs/`.
3. Request `GET /api/v1/auth/csrf/`, then log in through `POST /api/v1/auth/login/` with a staff account and the returned CSRF token.
4. Select **Authorize** and enter the returned access token in the Bearer field.
5. Create active brand and category entries first, or use IDs from their staff lists.
6. Create a required camera resolution definition through `POST /api/v1/staff/catalog/categories/{category_id}/specifications/`:

```json
{
  "key": "resolution",
  "label": "Resolution",
  "data_type": "choice",
  "unit": "",
  "is_required": true,
  "is_filterable": true,
  "is_displayed": true,
  "is_active": true,
  "sort_order": 0
}
```

7. Add one controlled value through `POST /api/v1/staff/catalog/specifications/{definition_id}/choices/`:

```json
{
  "value": "4mp",
  "label": "4 MP",
  "is_active": true,
  "sort_order": 0
}
```

8. Create a product through `POST /api/v1/staff/catalog/products/`. Use only accurate product information in real records:

```json
{
  "brand": 1,
  "category": 1,
  "sku": "DEMO-CAM-001",
  "slug": "demo-camera-001",
  "name": "Demo Camera Draft",
  "short_description": "Local API demonstration product.",
  "full_description": "Replace this demonstration text with approved product information.",
  "regular_price": "12500.00",
  "sale_price": null,
  "warranty_text": "Local test wording only.",
  "specifications": [
    {
      "definition": 1,
      "value": "4mp"
    }
  ]
}
```

9. Publish it through `PATCH /api/v1/staff/catalog/products/{product_id}/` with `{"is_published": true}`.
10. Without authorization, request `GET /api/v1/catalog/products/` and `GET /api/v1/catalog/products/demo-camera-001/`.

Use the IDs returned by your own API calls rather than assuming the example IDs exist. Lists use a page size of 20. Run the PostgreSQL catalog tests from `backend` with:

```powershell
python manage.py test apps.catalog --settings=config.settings.test
```
