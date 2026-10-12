import io
import json
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from email.message import Message
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from urllib.request import Request

from django.conf import settings
from django.test import SimpleTestCase
from PIL import Image

from scripts.smartlinks_products import (
    MAX_PAGE_BYTES,
    SourceRedirects,
    SmartlinksClient,
    download_images,
    extract_product,
    extract_urls,
    main,
    money,
    source_url,
    validate_image_batch,
    write_json,
)


PRODUCT_URL = "https://smartlinks.pk/product/test-camera/"
IMAGE_URL = "https://smartlinks.pk/wp-content/uploads/2026/01/camera.jpg"
HTML = """
<html><head><script type="application/ld+json">
{"@graph": [{"@type": "Product", "@id": "https://smartlinks.pk/product/test-camera/#product",
 "name": "SEO title", "sku": "TEST-001", "category": "Source brand",
 "offers": {"@type": "Offer", "price": "950.00", "priceCurrency": "PKR"}}]}
</script></head><body>
<nav><span class="price">PKR 99.00</span><img src="/logo.png"></nav>
<div class="woocommerce-product-gallery">
 <figure class="woocommerce-product-gallery__image"><a href="/wp-content/uploads/2026/01/camera.jpg">
 <img alt="Front view" src="/thumb.jpg" data-large_image="/wp-content/uploads/2026/01/camera.jpg"></a></figure>
 <figure class="woocommerce-product-gallery__image"><a href="/wp-content/uploads/2026/01/back.webp">
 <img alt="Back view" src="/thumb2.jpg"></a></figure>
</div>
<h1 class="product_title">Test Camera</h1>
<div class="wd-product-brands"><a href="/brand/source-brand/"><img alt="Source Brand"></a></div>
<div class="woocommerce-product-details__short-description"><p>Source description.</p>
 <ul><li>Source feature</li></ul><img src="/feature-icon.png"></div>
<div class="wd-single-price"><p class="price">
 <del><span class="woocommerce-Price-amount">₨1,000.00</span></del>
 <ins><span class="woocommerce-Price-amount">₨950.00</span></ins>
</p></div>
<span class="posted_in"><a>Indoor Cameras</a><a>Source Brand</a></span>
<div class="wd-single-content"><ul>
 <li><span class="tech-specs-items-description__title--heading">Camera</span></li>
 <li><span class="tech-specs-items-description__title">Resolution</span><span>1080p</span></li>
 <li><span class="tech-specs-items-description__title">Shutter</span><p>PAL: source value</p><p>NTSC: source value</p></li>
</ul></div>
<div id="tab-additional_information"><table><tr><th>Weight</th><td>1 kg</td></tr></table></div>
<section class="related"><p class="price">PKR 2000.00</p><img src="/related.jpg"></section>
</body></html>
"""


def response_headers(content_type):
    headers = Message()
    headers["Content-Type"] = content_type
    return headers


def image_bytes(image_format="JPEG"):
    output = io.BytesIO()
    Image.new("RGB", (24, 16), color="blue").save(output, format=image_format)
    return output.getvalue()


def image_batch(*urls):
    return {
        "schema_version": 1,
        "products": [{
            "source_url": PRODUCT_URL,
            "sku": "TEST-001",
            "reviewed": False,
            "pricing_approved": False,
            "images": [{"url": url, "alt_text": "", "local_path": None} for url in urls],
        }],
    }


class SmartlinksExtractionTests(SimpleTestCase):
    def test_extracts_visible_product_fields_without_related_prices_or_icons(self):
        product = extract_product(HTML, PRODUCT_URL)
        self.assertEqual(product["name"], "Test Camera")
        self.assertEqual(product["brand"], "Source Brand")
        self.assertEqual(product["sku"], "TEST-001")
        self.assertEqual(product["regular_price"], "1000.00")
        self.assertEqual(product["sale_price"], "950.00")
        self.assertEqual(product["currency"], "PKR")
        self.assertEqual(product["highlights"], ["Source feature"])
        self.assertEqual(product["short_description"], "Source description. Source feature")
        self.assertEqual(product["specifications"], [
            {"label": "Resolution", "value": "1080p", "source_section": "description"},
            {"label": "Shutter", "value": "PAL: source value NTSC: source value", "source_section": "description"},
            {"label": "Weight", "value": "1 kg", "source_section": "additional_information"},
        ])
        self.assertEqual([image["url"] for image in product["images"]], [
            IMAGE_URL, "https://smartlinks.pk/wp-content/uploads/2026/01/back.webp",
        ])
        self.assertTrue(all(image["local_path"] is None for image in product["images"]))
        self.assertIn("Visible title differs", product["warnings"][0])

    def test_missing_fields_are_null_and_review_is_required(self):
        product = extract_product('<h1 class="product_title">Test model</h1>', PRODUCT_URL)
        for field in ("brand", "sku", "manufacturer_model", "regular_price", "sale_price", "warranty_text"):
            self.assertIsNone(product[field])
        self.assertIsNone(product["category"])
        self.assertFalse(product["reviewed"])
        self.assertFalse(product["pricing_approved"])
        self.assertFalse(product["is_published"])
        self.assertEqual(product["stock_quantity"], 0)
        self.assertTrue(any("Missing sku" in warning for warning in product["warnings"]))

    def test_source_categories_are_candidates_and_not_assigned_automatically(self):
        product = extract_product(HTML, PRODUCT_URL)
        self.assertEqual(product["category_candidates"], ["Indoor Cameras", "Source Brand", "Source brand"])
        self.assertIsNone(product["category"])
        self.assertIsNone(product["manufacturer_model"])

    def test_product_schema_fallback_selects_only_the_requested_product(self):
        schema = [
            {"@type": "Product", "url": "https://smartlinks.pk/product/other/", "name": "Related product", "sku": "OTHER"},
            {
                "@type": "Product", "url": PRODUCT_URL, "name": "Schema Camera", "sku": "SCHEMA-1",
                "brand": {"name": "Schema Brand"}, "model": "Source Model",
                "offers": {"@type": "Offer", "price": "1234.50", "priceCurrency": "PKR"},
                "image": {"url": IMAGE_URL},
                "additionalProperty": {"name": "Audio", "value": "Source audio value"},
            },
        ]
        product = extract_product(f'<script type="application/ld+json">{json.dumps(schema)}</script>', PRODUCT_URL)
        self.assertEqual(product["name"], "Schema Camera")
        self.assertEqual(product["sku"], "SCHEMA-1")
        self.assertEqual(product["brand"], "Schema Brand")
        self.assertEqual(product["manufacturer_model"], "Source Model")
        self.assertEqual(product["regular_price"], "1234.50")
        self.assertEqual(product["images"][0]["url"], IMAGE_URL)
        self.assertEqual(product["specifications"][0]["label"], "Audio")

    def test_price_range_is_not_converted_to_an_invented_single_price(self):
        html = HTML.replace("<del>", "").replace("</del>", "").replace("<ins>", "").replace("</ins>", "")
        product = extract_product(html, PRODUCT_URL)
        self.assertIsNone(product["regular_price"])
        self.assertIsNone(product["sale_price"])
        self.assertTrue(any("price range" in warning for warning in product["warnings"]))

    def test_price_conflicts_and_long_short_descriptions_are_flagged(self):
        html = HTML.replace('"price": "950.00"', '"price": "900.00"').replace("Source description.", "x" * 501)
        product = extract_product(html, PRODUCT_URL)
        self.assertEqual(product["sale_price"], "950.00")
        self.assertTrue(any("prices differ" in warning for warning in product["warnings"]))
        self.assertTrue(any("500-character" in warning for warning in product["warnings"]))

    def test_invalid_schema_is_logged_and_a_blocked_page_is_rejected(self):
        product = extract_product('<h1 class="product_title">Camera</h1><script type="application/ld+json">invalid</script>', PRODUCT_URL)
        self.assertIn("Invalid JSON-LD was ignored.", product["warnings"])
        with self.assertRaisesMessage(ValueError, "No product title found"):
            extract_product("<h1>Access denied</h1>", PRODUCT_URL)

    def test_money_does_not_guess_missing_ranges_or_malformed_values(self):
        for value in (None, "Call for price", "1,000 - 2,000", "1,00", "-1", "1.001", "€100", "10000000000"):
            with self.subTest(value=value):
                self.assertIsNone(money(value))
        self.assertEqual(money("PKR 1,234.50"), "1234.50")

    def test_url_validation_rejects_unrelated_hosts_actions_and_unsafe_paths(self):
        for url in (
            "http://smartlinks.pk/product/test-camera/", "https://example.com/product/test-camera/",
            "https://user:password@smartlinks.pk/product/test-camera/", PRODUCT_URL + "?add-to-cart=1",
            PRODUCT_URL + "#section", "https://smartlinks.pk/wp-admin/", "https://smartlinks.pk:8000/product/test/",
            "https://smartlinks.pk/wp-content/uploads/%2e%2e/private.jpg",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                source_url(url, "image" if "uploads" in url else "product")
        self.assertEqual(source_url(PRODUCT_URL.rstrip("/"), "product"), PRODUCT_URL)

    def test_duplicate_urls_are_skipped_and_failed_rows_do_not_stop_other_rows(self):
        client = Mock()
        client.get.side_effect = [(HTML.encode(), response_headers("text/html; charset=utf-8")), URLError("Unavailable")]
        with redirect_stderr(io.StringIO()):
            batch = extract_urls([PRODUCT_URL, PRODUCT_URL.rstrip("/"), "https://smartlinks.pk/product/missing/"], client)
        self.assertEqual(len(batch["products"]), 1)
        self.assertEqual(len(batch["errors"]), 1)
        self.assertEqual(client.get.call_count, 2)

    def test_robots_disallow_and_unavailable_rules_prevent_product_requests(self):
        client = SmartlinksClient()
        with patch.object(client, "_request", return_value=(b"User-agent: *\nDisallow: /product/", response_headers("text/plain"))) as request:
            with self.assertRaisesMessage(ValueError, "disallowed"):
                client.get(PRODUCT_URL, "product")
            self.assertEqual(request.call_count, 1)
        client = SmartlinksClient()
        with patch.object(client, "_request", side_effect=URLError("Offline")) as request:
            with self.assertRaises(URLError):
                client.get(PRODUCT_URL, "product")
            self.assertEqual(request.call_count, 1)

    def test_robots_missing_file_allows_product_and_crawl_delay_is_respected(self):
        client = SmartlinksClient()
        missing = HTTPError("https://smartlinks.pk/robots.txt", 404, "Not found", {}, None)
        with patch.object(client, "_request", side_effect=[missing, (b"page", response_headers("text/html"))]):
            self.assertEqual(client.get(PRODUCT_URL, "product")[0], b"page")
        client = SmartlinksClient()
        with patch.object(client, "_request", return_value=(b"User-agent: *\nCrawl-delay: 3", response_headers("text/plain"))):
            client.check_allowed(PRODUCT_URL)
        self.assertEqual(client.delay, 3)

    def test_redirects_cannot_leave_the_source_host_or_fetch_another_path_type(self):
        redirect = SourceRedirects(Mock())
        request = Request(PRODUCT_URL)
        request.source_kind = "product"
        for url in ("https://example.com/product/test/", "https://smartlinks.pk/wp-admin/"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                redirect.redirect_request(request, None, 302, "Found", {}, url)

    def test_oversized_html_response_is_rejected(self):
        client = SmartlinksClient()
        response = client.opener = Mock()
        response.open.return_value.__enter__ = Mock(return_value=response)
        response.open.return_value.__exit__ = Mock(return_value=False)
        response.geturl.return_value = PRODUCT_URL
        response.read.return_value = b"x" * (MAX_PAGE_BYTES + 1)
        with self.assertRaisesMessage(ValueError, "exceeds"):
            client._request(PRODUCT_URL, "product", MAX_PAGE_BYTES)


class SmartlinksImageTests(SimpleTestCase):
    def setUp(self):
        self.temporary_root = settings.BASE_DIR / ".tmp"
        self.temporary_root.mkdir(exist_ok=True)

    def test_downloads_separate_validated_images_and_reruns_reuse_files(self):
        urls = [IMAGE_URL, IMAGE_URL.replace("camera.jpg", "back.png"), IMAGE_URL.replace("camera.jpg", "side.webp")]
        batch = image_batch(*urls)
        client = Mock()
        client.get.side_effect = [
            (image_bytes(image_format), response_headers(content_type))
            for image_format, content_type in (("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp"))
        ]
        with tempfile.TemporaryDirectory(dir=self.temporary_root) as directory, redirect_stderr(io.StringIO()):
            self.assertEqual(download_images(batch, client, directory), (3, 0))
            paths = [Path(directory) / image["local_path"] for image in batch["products"][0]["images"]]
            self.assertEqual([path.suffix for path in paths], [".jpg", ".png", ".webp"])
            self.assertTrue(all(path.is_file() and path.resolve().is_relative_to(Path(directory).resolve()) for path in paths))
            self.assertTrue(all(image["width"] == 24 and image["height"] == 16 for image in batch["products"][0]["images"]))
            self.assertEqual(download_images(batch, client, directory), (0, 3))
            self.assertEqual(client.get.call_count, 3)
            self.assertEqual(len(list(Path(directory).rglob("*.*"))), 3)
        self.assertFalse(batch["products"][0]["reviewed"])
        self.assertFalse(batch["products"][0]["pricing_approved"])
        self.assertEqual(batch["image_errors"], [])

    def test_rejects_invalid_mismatched_and_external_images_and_continues(self):
        batch = image_batch(IMAGE_URL, IMAGE_URL.replace("camera.jpg", "wrong.jpg"), "https://example.com/image.jpg", IMAGE_URL.replace("camera.jpg", "good.png"))
        client = Mock()
        client.get.side_effect = [
            (b"not an image", response_headers("image/jpeg")),
            (image_bytes("PNG"), response_headers("image/jpeg")),
            (image_bytes("PNG"), response_headers("image/png")),
        ]
        with tempfile.TemporaryDirectory(dir=self.temporary_root) as directory, redirect_stderr(io.StringIO()):
            self.assertEqual(download_images(batch, client, directory), (1, 0))
            self.assertEqual(len(list(Path(directory).rglob("*.png"))), 1)
            self.assertEqual(len(batch["image_errors"]), 3)
            self.assertTrue(all(image["local_path"] is None for image in batch["products"][0]["images"][:3]))

    def test_corrupt_cached_image_is_not_treated_as_a_successful_download(self):
        batch = image_batch(IMAGE_URL)
        client = Mock()
        client.get.return_value = image_bytes(), response_headers("image/jpeg")
        with tempfile.TemporaryDirectory(dir=self.temporary_root) as directory, redirect_stderr(io.StringIO()):
            download_images(batch, client, directory)
            cached = Path(directory) / batch["products"][0]["images"][0]["local_path"]
            cached.write_bytes(b"broken")
            self.assertEqual(download_images(batch, client, directory), (0, 0))
            self.assertIsNone(batch["products"][0]["images"][0]["local_path"])
            self.assertEqual(len(batch["image_errors"]), 1)

    def test_invalid_manifest_shape_is_rejected_before_downloading(self):
        for batch in ({}, {"schema_version": 1, "products": [None]}, image_batch(123)):
            with self.subTest(batch=batch), self.assertRaises(ValueError):
                validate_image_batch(batch)

    def test_json_write_protects_existing_review_file_and_cleans_temporary_files(self):
        with tempfile.TemporaryDirectory(dir=self.temporary_root) as directory:
            path = Path(directory) / "review.json"
            write_json(path, {"reviewed": True})
            with self.assertRaisesMessage(ValueError, "already exists"):
                write_json(path, {"reviewed": False})
            self.assertEqual(json.loads(path.read_text())["reviewed"], True)
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_cli_accepts_url_file_and_reports_partial_failure_with_nonzero_exit(self):
        client = Mock()
        client.get.return_value = HTML.encode(), response_headers("text/html; charset=utf-8")
        with tempfile.TemporaryDirectory(dir=self.temporary_root) as directory:
            urls = Path(directory) / "urls.txt"
            urls.write_text(f"# selected products\n\n{PRODUCT_URL}\nhttps://example.com/product/no/\n", encoding="utf-8")
            output = Path(directory) / "extracted.json"
            with patch("scripts.smartlinks_products.SmartlinksClient", return_value=client), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                result = main(["extract", "--urls-file", str(urls), "--output", str(output)])
            self.assertEqual(result, 1)
            batch = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(len(batch["products"]), 1)
            self.assertEqual(len(batch["errors"]), 1)

    def test_image_cli_does_not_overwrite_its_input_even_when_explicitly_overwriting_output(self):
        with tempfile.TemporaryDirectory(dir=self.temporary_root) as directory:
            path = Path(directory) / "extracted.json"
            original = image_batch(IMAGE_URL)
            write_json(path, original)
            with redirect_stderr(io.StringIO()):
                result = main(["images", "--input", str(path), "--output", str(path), "--image-root", directory, "--overwrite"])
            self.assertEqual(result, 1)
            self.assertEqual(json.loads(path.read_text()), original)
