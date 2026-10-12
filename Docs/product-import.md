# Import reviewed product data

`import_products` reads the version 1 JSON prepared by the [Smartlinks extraction
workflow](product-extraction.md). It creates draft products through the existing
catalog services. The command needs PostgreSQL and the configured Django media
storage, but does not need the development server or make network requests.

## Prepare the reviewed file

Copy extracted JSON to a separate `.tmp/smartlinks/reviewed.json`. For each
selected product:

1. Confirm its SKU, name, descriptions, factual specifications, and image usage.
2. Add an explicit stable product `slug` and choose one existing category.
3. Approve decimal-string regular/sale prices in `PKR`. A missing price cannot
   be imported, and the command never supplies a zero price as a fallback.
4. Map specification labels to the existing category's keys and typed values.
5. Set `reviewed: true` and `pricing_approved: true` as JSON booleans.
6. Keep `stock_quantity: 0` and `is_published: false`. Other values are rejected.

The following is an illustrative format, not approved inventory or pricing:

```json
{
  "schema_version": 1,
  "products": [
    {
      "source_url": "https://smartlinks.pk/product/example-camera/",
      "brand": "existing-brand-slug",
      "category": "existing-category-slug",
      "sku": "EXAMPLE-001",
      "slug": "example-camera",
      "name": "Reviewed product name",
      "short_description": "Reviewed source summary.",
      "full_description": "Reviewed source description.",
      "regular_price": "1000.00",
      "sale_price": null,
      "currency": "PKR",
      "warranty_text": null,
      "reviewed": true,
      "pricing_approved": true,
      "stock_quantity": 0,
      "is_published": false,
      "specifications": [
        {"key": "resolution", "value": "5mp"}
      ],
      "images": [
        {"local_path": "example-camera/front.png", "alt_text": "Front view of the reviewed camera"}
      ]
    }
  ]
}
```

Use actual existing slugs, definition keys, and choice values from the staff
catalog APIs. Raw `{label, value, source_section}` extraction entries need a
reviewed `key`; the command does not guess mappings. Other extraction metadata
may stay in the review file. `manufacturer_model` is informational: the existing
Product model identifies models through SKU/name, without a separate model field.
`warranty_text: null` means no supplied warranty wording and becomes an empty
field, not a fabricated warranty.

## Reuse or explicitly create taxonomy and specifications

Brand/category strings match an existing slug or name case-insensitively.
Ambiguous, conflicting, or inactive entries produce an error. Existing entries
are never edited or reactivated by import. For a missing entry, provide:

```json
{"name": "Approved new brand", "slug": "approved-new-brand", "create": true}
```

Specification definitions are resolved by the selected category and normalized
`key`. Existing data types and units cannot be changed by import. If you provide
`data_type` or `unit`, it must match the existing definition; its existing label
is retained. Values must match the definition's type: non-empty strings for
text, JSON integers for integer, decimal strings for decimal, JSON booleans for
boolean, and existing choice slugs for choice.

To create a reviewed missing definition, add explicit creation information:

```json
{
  "key": "approved-feature",
  "label": "Approved feature",
  "data_type": "text",
  "unit": "",
  "create": true,
  "value": "Reviewed source value"
}
```

New definitions use the model's existing defaults: optional, active, displayed,
and not filterable. Required/filter behavior remains a deliberate staff API edit.
For a missing choice on a choice definition, use `create_choice: true` and an
explicit `choice_label` alongside the approved `value`. Existing choices are
retained; inactive or unknown choices fail validation. Repeated keys are rejected.

## Dry run, then import

From `backend/`, substitute the email of your existing active staff user:

```powershell
.venv\Scripts\python.exe manage.py import_products ..\.tmp\smartlinks\reviewed.json --actor staff@example.com --image-root ..\.tmp\smartlinks\images --dry-run --report ..\.tmp\smartlinks\dry-run-report.json
```

Dry runs validate models, prices, specifications, local images, and conflicts
between rows in a transaction that is rolled back. No product, taxonomy,
specification, image record, audit event, or uploaded file is retained. Normal
database sequence allocation can still occur; the JSON report contains no
simulated product IDs. A dry run writes only its local report.

After resolving errors, run without `--dry-run` and use a new report path:

```powershell
.venv\Scripts\python.exe manage.py import_products ..\.tmp\smartlinks\reviewed.json --actor staff@example.com --image-root ..\.tmp\smartlinks\images --report ..\.tmp\smartlinks\import-report.json
```

Each product has its own database transaction. Successful rows are retained if
other rows fail. Product creation, reviewed new taxonomy/definitions/choices,
specification values, image records, and the `PRODUCT_IMPORTED` audit event commit
together. Real imports own their commit boundary; the service rejects enclosing
transactions that could roll back its referenced image files later.

The audit event identifies the staff actor, source URL, extraction time, review
and pricing approval flags, imported prices, and SHA-256 digest of the reviewed
input file. Imported products remain unpublished with zero stock and no stock
movement. Verify real stock through the inventory API, then explicitly publish
through the existing validated staff product API. Approval here applies to the
prices in the reviewed import; subsequent staff price changes use the existing
price audit workflow.

## Local images and reruns

Image downloads remain separate. The importer never fetches remote image URLs
and never trusts the extraction file's absolute `image_root`. Specify
`--image-root` explicitly when an image has a `local_path`. Paths must be relative
to that directory, refer to existing files, and stay inside it after symlink
resolution. JPEG, PNG, and WebP files use the existing 5 MB decoder/dimension
validation and configured Django storage. Each local image needs non-empty
`alt_text` of at most 255 characters. Repeated local files are rejected.

Images retain array order; the first imported image is primary. Entries with
`local_path: null` are reported as skipped references. Use `images: []` to import
product data alone, and attach images later through the existing staff image API.
This is also how you add photos after a product has already been imported.

SKUs are trimmed, uppercased, and checked case-insensitively. An existing SKU is
skipped without changing its price, stock, publication, specifications, or images.
Duplicate rows and concurrent imports cannot create a second product with that
SKU. A failed row rolls back its new records and deletes its successfully uploaded
files through their storage backend; cleanup failures are logged. Original local
photos are retained. Fix the failed rows and rerun with a new report path.

## Reports and checks

The report defaults to `INPUT.import-report.json`; `--report` selects another
path. Existing reports and the reviewed input are protected from overwrite.
Report access is checked before catalog writes. Reports contain `dry_run`, counts
of `created`, `validated`, `skipped`, and `error`, and per-row results with SKU,
product ID, image counts, reasons, or validation errors. Errors are also logged
and printed to stderr. Any failed row returns a nonzero exit code. JSON, actor,
and root errors stop before catalog writes; successful per-product imports are
not undone by a later report-write failure, so rerunning remains safe.

From `backend/`:

```powershell
.venv\Scripts\python.exe manage.py test apps.catalog.tests.test_product_import --settings=config.settings.test
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

The importer adds no API endpoint, database model/migration, dependency, or
frontend change. PostgreSQL tests cover staff attribution, review/price guards,
duplicates, typed specifications, local image validation, dry runs, row/file
rollback, command reports, and concurrent imports of the same SKU.
