# Prepare Smartlinks product data

This offline tool is the first stage of bulk catalog import. It reads only the
Smartlinks product URLs you supply and saves JSON for manual review. It does not
create products, change inventory, approve prices, or publish anything. The
Django management command that imports reviewed JSON is a separate next slice.

Use the existing backend virtual environment. Extraction uses Python's standard
library; the optional image step also uses the installed Django/Pillow catalog
image validator. Neither command needs PostgreSQL or a running Django server.

## Extract selected products

From the repository root, create `.tmp/smartlinks/urls.txt` with one direct HTTPS
product URL per line. Blank lines and lines starting with `#` are ignored. Keep
the URL list and generated files in `.tmp/`, which is excluded from Git.

```powershell
backend\.venv\Scripts\python.exe backend\scripts\smartlinks_products.py extract --urls-file .tmp\smartlinks\urls.txt --output .tmp\smartlinks\extracted.json
```

You can also supply URLs directly:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\smartlinks_products.py extract "https://smartlinks.pk/product/hikvision-5mp-fixed-bullet-camera-2/" --output .tmp\smartlinks\single-product.json
```

Requests are sequential with at least one second between them. The tool respects
`robots.txt`, including crawl delays, and rejects unrelated hosts, unsafe paths,
query strings, and redirects outside the permitted source paths. A missing
robots file (HTTP 404) allows access; other failures to verify access prevent the
source request. There is no login, CAPTCHA, or access-control bypass. Use source
material only where you have permission to use it; downloadable images still
need approval for use in your store.

The parser prefers the visible product title, single-product price block, and
main gallery. JSON-LD provides available fallback fields. Navigation, feature
icons, brand logos, and related-product images are excluded. Layout changes or
missing fields produce warnings/errors rather than invented values. Price ranges
and multiple offers are left for manual review.

## Review the JSON

The versioned document contains `products`, an extraction timestamp, and
per-URL `errors`. Each product includes:

- Source URL and a SHA-256 digest of the decoded HTML encoded as UTF-8.
- Name, available brand, SKU, explicit manufacturer model, and descriptions.
- `category_candidates`; `category` stays `null` until you choose one OctaCam
  category. Source categories may be brand names or parent groups.
- Specifications as `{label, value, source_section}` entries, preserving source
  text for later mapping to OctaCam's typed definitions. Technical description
  and additional-information entries remain distinguishable.
- Decimal-string regular/sale prices and source currency. No price approval is
  inferred from extraction. Conflicting prices are flagged.
- Ordered `images` entries containing `url`, source `alt_text`, and initially
  `local_path: null`.
- `reviewed: false`, `pricing_approved: false`, `stock_quantity: 0`, and
  `is_published: false`. These are safe preparation defaults, not claims about
  source inventory. `warranty_text` stays `null`; supplied warranty wording in
  descriptions still needs explicit review.
- `warnings`, including missing fields and descriptions exceeding the backend's
  500-character short-description limit. Text is not silently truncated.

Copy the extraction output to a separate review file. Confirm the actual model,
SKU, factual descriptions/specifications, brand/category mapping, approved PKR
prices, and image usage. Missing values remain `null`; do not fill them with
guesses. A model is not automatically inferred from a SKU or title. These raw
specification labels still need mapping to existing category-specific definitions
before the later importer can accept them.

Existing JSON files are protected from accidental replacement. Use a new output
filename or explicitly pass `--overwrite`; keep reviewed files separate from
fresh extraction output.

## Download images separately

Extraction never downloads image binaries. Run this optional second command:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\smartlinks_products.py images --input .tmp\smartlinks\extracted.json --image-root .tmp\smartlinks\images --output .tmp\smartlinks\with-images.json
```

The command reads only the listed main-gallery URLs under Smartlinks' uploads
directory. Each product gets a deterministic folder based on its SKU (or source
slug) and URL digest. Filenames retain gallery order and use a URL digest. Files
are staged outside the live catalog media directory. The backend's existing
validator accepts JPEG, PNG, and WebP up to 5 MB, checks decoding and dimension
limits, rejects animation, and normalizes orientation/metadata before saving.

The new JSON records `image_root`, image paths relative to that root, dimensions,
and file hashes. It also records per-image `image_errors`; failed images have
`local_path: null`. The input JSON remains untouched. Reruns reuse validated
staged files without duplicating or overwriting them; use a new image root to
refresh source images. Prices and review flags are preserved.

You can use your own approved local photos instead: skip the download command,
stage them in your chosen image directory, and set each `local_path` and meaningful
`alt_text` in the review JSON. Leave `url` as the source reference where one
exists. Gallery order determines the primary image. Staged files are not visible
on the storefront until they are imported through the existing product image
service.

Both commands log progress/errors to stderr, save successful results even when
some requests fail, and exit with status 1 on failures (0 on success). Review the
JSON error arrays before continuing. Validation warnings alone do not change the
exit status; they require human review. No retry loop is used for blocked pages.

## Verification

From `backend/`:

```powershell
.venv\Scripts\python.exe manage.py test apps.catalog.tests.test_smartlinks_extraction --settings=config.settings.test
```

These tests use synthetic source pages and mocked network responses. They verify
extraction boundaries, price ambiguity, missing data, robots/redirect rules,
partial failure reporting, image validation and reruns, and protection of input
and review files. They use `SimpleTestCase` and do not write database records.
