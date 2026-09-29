# Trying the product catalog API

The catalog API lets staff define technical attributes per category, prepare products, manage images, publish records, and adjust stock. Public endpoints expose only published products whose brand and category are active. Public discovery supports search, filters, sorting, and filter metadata.

## Routes

All paths start with `/api/v1/`.

| Method | Path | Access and behavior |
| --- | --- | --- |
| GET | `catalog/products/` | Anyone; paginated search, filter, and sort of published products |
| GET | `catalog/filters/` | Anyone; available category, brand, price, and category-specific specification filters |
| GET | `catalog/products/{slug}/` | Anyone; one published product with displayed specifications |
| GET, POST | `staff/catalog/products/` | Staff; list products or create an unpublished draft |
| GET, PATCH | `staff/catalog/products/{id}/` | Staff; retrieve/edit, replace specifications, publish, or unpublish |
| POST | `staff/catalog/products/{id}/images/` | Staff; upload a product image with alt text and optional order |
| PATCH, DELETE | `staff/catalog/product-images/{id}/` | Staff; replace image, edit alt text, reorder, or remove |
| GET, POST | `staff/catalog/products/{id}/stock-adjustments/` | Staff; paginated stock history or a reasoned stock adjustment |
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

Public product details include active values whose definitions have `is_displayed: true`. Only active definitions with `is_filterable: true` appear as technical filters. Text specifications are displayed but not filterable.

## Public discovery

`GET /api/v1/catalog/products/` accepts `q` for case-insensitive product name or full/partial SKU search. `brand` and `category` take slugs. `min_price` and `max_price` compare the current selling price (sale price when present, otherwise regular price), inclusive. `availability` is `in_stock` or `out_of_stock`. `sort` is `relevance` (default), `price_asc`, or `price_desc`. Exact SKU, SKU prefix, name prefix, and other partial matches are prioritized in that order for relevance. Ties use name then ID; price ties use ID. `page` uses the configured page size of 20 and the normal `count`, `next`, `previous`, `results` response.

Select `category` before using `spec_<key>` parameters. Active choice filters take a choice value, boolean filters take `true` or `false`, and integer/decimal ranges take `spec_<key>_min` and/or `spec_<key>_max`. Technical filters from another category, inactive or non-filterable definitions, invalid choices, unknown parameters, and invalid ranges return the shared 400 validation error. Multiple filters combine with AND. Published out-of-stock products remain visible unless `availability=in_stock` is requested.

For example:

```text
GET /api/v1/catalog/products/?q=ds-2ce&brand=hikvision&category=cameras&min_price=5000&max_price=20000&availability=in_stock&spec_resolution=2mp&spec_ir_distance_min=20&sort=price_asc&page=1
```

`GET /api/v1/catalog/filters/?category=cameras` returns `brand` and `category` options, `price` bounds, and filterable `specifications`. Choices and boolean options contain only values on published products in the current scope; integer and decimal filters give observed bounds. Definitions without observed values are omitted. An empty scope has `null` price bounds. Without a category, `specifications` is empty. Metadata accepts `brand` and `category` to scope the options. Brand options are based on the selected category; category options are based on the selected brand, so shoppers can switch facets. Price and technical options use both selected facets. The metadata endpoint does not take search, price, availability, or technical filters.

## Publication rules

Product creation always produces `is_published: false` with `stock_quantity: 0`. `is_published` is rejected during creation, and `stock_quantity` cannot be changed through ordinary product POST/PATCH.

Staff publish an existing product with:

```json
{
  "is_published": true
}
```

The brand and category must be active, core product fields must be complete, prices must be valid, and every active required specification for the category must have a valid value. A failed publication returns 400 and leaves the product as a draft. Editing a published product cannot make it incomplete. Publishing and unpublishing create `PRODUCT_PUBLISHED` and `PRODUCT_UNPUBLISHED` audit events in the same transaction.

Publication is separate from availability. A published product remains in public list and detail responses when `stock_quantity` is zero, with `is_in_stock: false`.

## Staff stock adjustments and history

Use `POST /api/v1/staff/catalog/products/{id}/stock-adjustments/` with a Bearer staff token:

```json
{
  "new_quantity": 17,
  "reason": "Physical stock count correction"
}
```

`new_quantity` is the absolute quantity after the adjustment, from 0 through 2,147,483,647. The reason is required, trimmed, and limited to 500 characters. An unchanged quantity is rejected. The server locks the product row and atomically updates stock, writes an inventory movement, and writes a `PRODUCT_STOCK_ADJUSTED` audit event. A failed request leaves all three unchanged. The movement stores the previous quantity, new quantity, signed delta, staff actor, and time. Its `movement_type` is `manual_adjustment`; the response's `reason` is the staff explanation. Public product stock changes immediately, including when it reaches zero.

Use `GET` on the same URL for newest-first history in the standard `count`, `next`, `previous`, `results` format. Anonymous visitors receive 401, customers receive 403, and missing products receive 404. The `actor` field is the staff user ID. Future checkout and cancellation workflows will add their own movement kinds and order linkage; they are not part of this endpoint.

## Product images

Send uploads as `multipart/form-data` with an `image` file and descriptive, nonblank `alt_text`. You may supply a nonnegative `sort_order`; otherwise the new image is placed after existing images. Each product uses each order value at most once. A PATCH to an occupied order swaps those two images. The image with the lowest order is primary. A PATCH may also replace the file; DELETE removes its record and cleans up its stored file after the database commit.

JPEG, PNG, and WebP are accepted, up to 5 MB and 6000 pixels per side, with no more than 24 million pixels total. The server checks the declared type against decoded image content, rejects malformed or animated files, and rewrites accepted images to remove embedded metadata. Original filenames are discarded. Public list responses contain `primary_image` or `null`; public details contain ordered `images`. Each image supplies an ID, `image_url`, `alt_text`, order, dimensions, and creation time. Staff product responses also include the ordered images.

Locally, image files are stored in ignored `backend/media/products/{product_id}/` with random names. With `DEBUG=True`, Django serves the returned `/media/...` URLs. The database stores the storage key and image metadata, while production must configure object storage before it can run. No provider package or credentials are selected in this slice.

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
11. In Swagger, execute `POST /api/v1/staff/catalog/products/{product_id}/images/`, select a local JPEG/PNG/WebP file for `image`, and enter `alt_text` such as `Front view of the camera`. Use the returned ID with `PATCH /api/v1/staff/catalog/product-images/{id}/` to edit alt text or order. The public detail response then shows the image URL and dimensions.
12. Request `GET /api/v1/catalog/filters/?category=cameras` to inspect available filter keys and values. Then try `GET /api/v1/catalog/products/?category=cameras&spec_resolution=4mp&sort=price_asc`. The zero-stock demo product remains in the results unless you add `availability=in_stock`.
13. With the staff token, send `POST /api/v1/staff/catalog/products/{product_id}/stock-adjustments/` using the example above. Send `GET` to that same URL to inspect movement history, then revisit the public product detail to see the current stock.

Use the IDs returned by your own API calls rather than assuming the example IDs exist. Lists use a page size of 20. Run the PostgreSQL catalog tests from `backend` with:

```powershell
python manage.py test apps.catalog --settings=config.settings.test
```
