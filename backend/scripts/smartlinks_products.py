"""Extract selected Smartlinks product pages and optionally stage their gallery images."""

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.robotparser import RobotFileParser


USER_AGENT = "OctaCamProductReview/1.0"
MAX_PAGE_BYTES = 4 * 1024 * 1024
MAX_IMAGE_BYTES = 5 * 1024 * 1024
IMAGE_TYPES = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


def source_url(value, kind):
    """Allow explicit HTTPS product URLs and source-host media, never arbitrary hosts."""
    parts = urlsplit(value)
    if (
        parts.scheme != "https"
        or parts.hostname not in {"smartlinks.pk", "www.smartlinks.pk"}
        or parts.username is not None
        or parts.password is not None
        or parts.port not in {None, 443}
        or parts.query
        or parts.fragment
        or "\\" in unquote(parts.path)
        or any(segment in {".", ".."} for segment in unquote(parts.path).split("/"))
    ):
        raise ValueError("Use a direct HTTPS Smartlinks URL without credentials, query, or fragment.")
    path = parts.path
    allowed = {
        "product": bool(re.fullmatch(r"/product/[^/]+/?", path)),
        "image": path.startswith("/wp-content/uploads/"),
        "robots": path == "/robots.txt",
    }
    if not allowed.get(kind):
        raise ValueError(f"Not a permitted Smartlinks {kind} URL: {value}")
    if kind == "product":
        path = path.rstrip("/") + "/"
    return urlunsplit(("https", parts.hostname, path, "", ""))


class SourceRedirects(HTTPRedirectHandler):
    def __init__(self, client):
        self.client = client

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        kind = req.source_kind
        newurl = source_url(newurl, kind)
        if kind != "robots":
            self.client.check_allowed(newurl)
        self.client.wait_between_requests()
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None:
            redirected.source_kind = kind
        return redirected


class SmartlinksClient:
    """Sequential, bounded requests with robots checks and no access-control bypass."""

    def __init__(self, *, delay=1.0, timeout=20):
        self.delay = delay
        self.timeout = timeout
        self.robots = {}
        self.last_request = None
        self.opener = build_opener(SourceRedirects(self))

    def wait_between_requests(self):
        if self.last_request is not None:
            time.sleep(max(0, self.delay - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()

    def _request(self, url, kind, max_bytes):
        self.wait_between_requests()
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"})
        request.source_kind = kind
        with self.opener.open(request, timeout=self.timeout) as response:
            source_url(response.geturl(), kind)
            body = response.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise ValueError(f"Response exceeds the {max_bytes / (1024 * 1024):g} MB limit.")
            return body, response.headers

    def check_allowed(self, url):
        parts = urlsplit(url)
        origin = f"https://{parts.hostname}"
        if origin not in self.robots:
            parser = RobotFileParser()
            try:
                body, headers = self._request(origin + "/robots.txt", "robots", 128 * 1024)
                if headers.get_content_type() not in {"text/plain", "application/octet-stream"}:
                    raise ValueError("Cannot verify robots.txt: expected a text response.")
                parser.parse(body.decode("utf-8-sig").splitlines())
            except HTTPError as exc:
                if exc.code != 404:
                    raise ValueError(f"Cannot verify robots.txt (HTTP {exc.code}); source skipped.") from exc
                parser.parse([])
            self.robots[origin] = parser
            self.delay = max(self.delay, parser.crawl_delay(USER_AGENT) or 0)
            rate = parser.request_rate(USER_AGENT)
            if rate:
                self.delay = max(self.delay, rate.seconds / rate.requests)
        if not self.robots[origin].can_fetch(USER_AGENT, url):
            raise ValueError("Source path is disallowed by robots.txt.")

    def get(self, url, kind):
        url = source_url(url, kind)
        self.check_allowed(url)
        return self._request(url, kind, MAX_PAGE_BYTES if kind == "product" else MAX_IMAGE_BYTES)


@dataclass
class Node:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()

    def has_class(self, name):
        return name in self.attrs.get("class", "").split()

    def text(self, *, exclude=None):
        if self is exclude or self.tag in {"script", "style"}:
            return ""
        return re.sub(r"\s+", " ", " ".join(
            part for child in self.children
            if (part := child.text(exclude=exclude) if isinstance(child, Node) else child.strip())
        )).strip()


class ProductHTML(HTMLParser):
    VOID_TAGS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
        "param", "source", "track", "wbr",
    }

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.stack = [self.root]
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in self.VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def first(nodes, *, css_class=None, tag=None, node_id=None):
    return next((node for node in nodes if (
        (css_class is None or node.has_class(css_class))
        and (tag is None or node.tag == tag)
        and (node_id is None or node.attrs.get("id") == node_id)
    )), None)


def plain_text(value):
    return ProductHTML(str(value)).root.text() if value is not None else None


def money(value):
    if value is None:
        return None
    text = re.sub(r"^(?:PKR|Rs\.?|₨)\s*", "", str(value).strip(), flags=re.I).strip()
    if not re.fullmatch(r"(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?", text):
        return None
    try:
        price = Decimal(text.replace(",", ""))
        return format(price, ".2f") if price <= Decimal("9999999999.99") else None
    except InvalidOperation:
        return None


def schema_products(nodes, warnings):
    def visit(value):
        if isinstance(value, dict):
            kind = value.get("@type", [])
            if kind == "Product" or isinstance(kind, list) and "Product" in kind:
                yield value
            for child in value.values():
                yield from visit(child)
        elif isinstance(value, list):
            for child in value:
                yield from visit(child)

    products = []
    for node in nodes:
        if node.tag == "script" and node.attrs.get("type") == "application/ld+json":
            try:
                products.extend(visit(json.loads("".join(c for c in node.children if isinstance(c, str)))))
            except (ValueError, TypeError):
                warnings.append("Invalid JSON-LD was ignored.")
    return products


def extract_product(html, url):
    url = source_url(url, "product")
    nodes = list(ProductHTML(html).root.walk())
    warnings = []
    title = first(nodes, css_class="product_title", tag="h1")
    candidates = schema_products(nodes, warnings)
    matching = []
    for candidate in candidates:
        references = [candidate.get("url"), candidate.get("@id"), candidate.get("mainEntityOfPage")]
        if any(
            isinstance(reference := ref.get("@id") if isinstance(ref, dict) else ref, str)
            and reference.split("#")[0].rstrip("/") == url.rstrip("/")
            for ref in references
        ):
            matching.append(candidate)
    structured = matching[0] if len(matching) == 1 else candidates[0] if len(candidates) == 1 else {}
    if len(candidates) > 1 and len(matching) != 1:
        warnings.append("Multiple structured products found; ambiguous JSON-LD was ignored.")
    name = title.text() if title else plain_text(structured.get("name"))
    if not name:
        raise ValueError("No product title found; this may be a blocked page or a changed layout.")
    if title and structured.get("name") and name != plain_text(structured["name"]):
        warnings.append("Visible title differs from JSON-LD; the visible product title was used.")

    short = first(nodes, css_class="woocommerce-product-details__short-description")
    full = first(nodes, node_id="tab-description") or first(nodes, css_class="wd-single-content")
    sku_node = first(nodes, css_class="sku")
    brand_node = first(nodes, css_class="wd-product-brands")
    brand = structured.get("brand")
    brand = brand.get("name") if isinstance(brand, dict) else brand if isinstance(brand, str) else None
    if brand_node:
        image = first(brand_node.walk(), tag="img")
        brand = (image.attrs.get("alt") or image.attrs.get("title")) if image else brand_node.text() or brand
    category_node = first(nodes, css_class="posted_in")
    categories = [n.text() for n in category_node.walk() if n.tag == "a"] if category_node else []
    schema_category = structured.get("category")
    if isinstance(schema_category, str) and schema_category:
        categories.append(schema_category)

    # Only the single-product price block; navigation and related-item prices are excluded.
    price_container = first(nodes, css_class="wd-single-price") or first(nodes, css_class="summary")
    price = first(price_container.walk(), css_class="price") if price_container else first(nodes, tag="p", css_class="price")
    regular = sale = None
    if price:
        original = first(price.walk(), tag="del")
        discounted = first(price.walk(), tag="ins")
        amounts = [node for node in price.walk() if node.has_class("woocommerce-Price-amount")]
        if original and discounted:
            regular, sale = money(original.text()), money(discounted.text())
        elif len(amounts) == 1:
            regular = money(amounts[0].text())
        elif len(amounts) > 1:
            warnings.append("Multiple prices or a price range found; choose an approved price manually.")
        else:
            regular = money(price.text())
    offers = structured.get("offers", {})
    offers = offers[0] if isinstance(offers, list) and len(offers) == 1 else offers
    offers = offers if isinstance(offers, dict) and offers.get("@type") != "AggregateOffer" else {}
    currency = offers.get("priceCurrency")
    if not currency:
        currency_meta = next((
            n for n in nodes
            if n.tag == "meta" and n.attrs.get("property") == "product:price:currency"
        ), None)
        currency = currency_meta.attrs.get("content") if currency_meta else None
    if not price:
        regular = money(offers.get("price"))
    listed = sale or regular
    if listed and offers.get("price") is not None and listed != money(offers["price"]):
        warnings.append("Visible and structured prices differ; verify the listed prices.")
    if sale is not None and (regular is None or Decimal(sale) >= Decimal(regular)):
        warnings.append("Sale price is not below the regular price; correct it during review.")

    specifications = []
    for section in [full, first(nodes, node_id="tab-additional_information")]:
        if section is None:
            continue
        for item in section.walk():
            label = first(item.walk(), css_class="tech-specs-items-description__title") if item.tag == "li" else None
            if item.tag == "tr":
                label = first(item.walk(), tag="th")
            if label:
                value = item.text(exclude=label)
                if value:
                    specifications.append({
                        "label": label.text(),
                        "value": value,
                        "source_section": (
                            "additional_information" if section.attrs.get("id") == "tab-additional_information"
                            else "description"
                        ),
                    })
    properties = structured.get("additionalProperty") or []
    properties = properties if isinstance(properties, list) else [properties]
    for item in properties:
        if isinstance(item, dict) and item.get("name") and item.get("value") is not None:
            entry = {
                "label": plain_text(item["name"]), "value": plain_text(item["value"]),
                "source_section": "structured_data",
            }
            if not any(s["label"] == entry["label"] and s["value"] == entry["value"] for s in specifications):
                specifications.append(entry)

    images = []
    gallery = first(nodes, css_class="woocommerce-product-gallery")
    if gallery:
        for node in gallery.walk():
            if node.has_class("woocommerce-product-gallery__image"):
                image, link = first(node.walk(), tag="img"), first(node.walk(), tag="a")
                reference = (image.attrs.get("data-large_image") or image.attrs.get("data-src")) if image else None
                reference = reference or (link.attrs.get("href") if link else None)
                reference = reference or (image.attrs.get("src") if image else None)
                if reference:
                    images.append({
                        "url": urljoin(url, reference),
                        "alt_text": image.attrs.get("alt", "") if image else "",
                        "local_path": None,
                    })
    if not images:
        references = structured.get("image", [])
        references = references if isinstance(references, list) else [references]
        for reference in references:
            reference = reference.get("url") or reference.get("contentUrl") if isinstance(reference, dict) else reference
            if isinstance(reference, str):
                images.append({"url": urljoin(url, reference), "alt_text": "", "local_path": None})
    images = list({image["url"]: image for image in images}.values())
    sku = sku_node.text() if sku_node and sku_node.text() not in {"N/A", ""} else structured.get("sku")
    model = structured.get("model")
    model = model.get("name") if isinstance(model, dict) else model if isinstance(model, str) else None
    model = model or next((
        s["value"] for s in specifications if s["label"].lower().strip(": ") in {"model", "model number"}
    ), None)
    result = {
        "source_url": url,
        "source_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
        "name": name,
        "brand": brand or None,
        "category": None,
        "category_candidates": list(dict.fromkeys(categories)),
        "sku": str(sku).strip() if sku is not None else None,
        "manufacturer_model": model,
        "short_description": short.text() if short else None,
        "full_description": full.text() if full else plain_text(structured.get("description")),
        "highlights": [n.text() for n in short.walk() if n.tag == "li"] if short else [],
        "specifications": specifications,
        "regular_price": regular,
        "sale_price": sale,
        "currency": currency,
        "warranty_text": None,
        "images": images,
        "reviewed": False,
        "pricing_approved": False,
        "stock_quantity": 0,
        "is_published": False,
        "warnings": warnings,
    }
    for key in ("brand", "sku", "manufacturer_model", "short_description", "full_description", "regular_price"):
        if not result[key]:
            warnings.append(f"Missing {key}; review manually, no value was invented.")
    if currency != "PKR":
        warnings.append("Currency is missing or is not PKR; verify before approving prices.")
    if result["short_description"] and len(result["short_description"]) > 500:
        warnings.append("Short description exceeds the backend's 500-character limit; edit during review.")
    if not specifications:
        warnings.append("No structured specifications found; inspect the source description.")
    if not images:
        warnings.append("No product gallery images found.")
    warnings.append("Choose one OctaCam category; source categories may include brands or parent groups.")
    return result


def prepare_downloaded_image(body, content_type):
    """Reuse catalog validation and normalization without opening a database connection."""
    backend = str(Path(__file__).resolve().parents[1])
    if backend not in sys.path:
        sys.path.insert(0, backend)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    import django
    django.setup()
    from django.core.files.uploadedfile import SimpleUploadedFile
    from apps.catalog.image_services import prepare_product_image

    content, extension, width, height = prepare_product_image(
        SimpleUploadedFile("source-image", body, content_type=content_type),
    )
    return content.read(), extension, width, height


def write_json(path, data, *, overwrite=False):
    path = Path(path)
    if path.exists() and not overwrite:
        raise ValueError(f"Output already exists: {path}. Use a new path or --overwrite.")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def extract_urls(urls, client):
    batch = {
        "schema_version": 1,
        "source_site": "Smartlinks.pk",
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "products": [],
        "errors": [],
    }
    seen = set()
    for raw_url in urls:
        try:
            url = source_url(raw_url, "product")
            if url in seen:
                continue
            seen.add(url)
            body, headers = client.get(url, "product")
            if headers.get_content_type() not in {"text/html", "application/xhtml+xml"}:
                raise ValueError("Expected an HTML product page.")
            product = extract_product(body.decode(headers.get_content_charset() or "utf-8"), url)
            batch["products"].append(product)
            print(f"Extracted: {product['name']}", file=sys.stderr)
        except (ValueError, OSError, UnicodeError, URLError) as exc:
            batch["errors"].append({"source_url": raw_url, "error": str(exc)})
            print(f"Failed: {raw_url}: {exc}", file=sys.stderr)
    return batch


def download_images(batch, client, image_root):
    from rest_framework.exceptions import ValidationError

    root = Path(image_root).resolve()
    downloaded = reused = 0
    batch["image_errors"] = []
    for product in batch["products"]:
        url = product["source_url"]
        source_name = product.get("sku") or urlsplit(url).path.strip("/").rsplit("/", 1)[-1]
        folder_name = re.sub(r"[^a-z0-9-]+", "-", str(source_name).lower()).strip("-")[:80] or "product"
        folder = root / f"{folder_name}-{hashlib.sha256(url.encode()).hexdigest()[:12]}"
        for index, image in enumerate(product.get("images", []), 1):
            try:
                image_url = source_url(image["url"], "image")
                basename = f"{index:02d}-{hashlib.sha256(image_url.encode()).hexdigest()[:12]}"
                existing = next((
                    folder / f"{basename}.{ext}" for ext in IMAGE_TYPES
                    if (folder / f"{basename}.{ext}").exists()
                ), None)
                if existing:
                    if existing.resolve().parent != folder.resolve() or not existing.resolve().is_relative_to(root):
                        raise ValueError("Cached image escapes the image directory.")
                    if existing.stat().st_size > MAX_IMAGE_BYTES:
                        raise ValueError("Cached image exceeds the 5 MB limit.")
                    body, extension, width, height = prepare_downloaded_image(
                        existing.read_bytes(), IMAGE_TYPES[existing.suffix[1:]],
                    )
                    destination = existing
                    reused += 1
                else:
                    body, headers = client.get(image_url, "image")
                    body, extension, width, height = prepare_downloaded_image(body, headers.get_content_type())
                    folder.mkdir(parents=True, exist_ok=True)
                    if folder.resolve().parent != root:
                        raise ValueError("Image directory escapes the requested root.")
                    destination = folder / f"{basename}.{extension}"
                    # Exclusive creation never overwrites an existing file, including a symlink.
                    created = False
                    try:
                        with destination.open("xb") as handle:
                            created = True
                            handle.write(body)
                    except OSError:
                        if created:
                            destination.unlink(missing_ok=True)
                        raise
                    downloaded += 1
                image.update(
                    local_path=destination.relative_to(root).as_posix(), width=width, height=height,
                    sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
                )
                print(f"Image ready: {image['local_path']}", file=sys.stderr)
            except (ValueError, OSError, URLError, ValidationError) as exc:
                image["local_path"] = None
                for field_name in ("width", "height", "sha256"):
                    image.pop(field_name, None)
                batch["image_errors"].append({"source_url": url, "image_url": image.get("url"), "error": str(exc)})
                print(f"Image failed: {image.get('url')}: {exc}", file=sys.stderr)
    batch["images_downloaded_at"] = datetime.now(timezone.utc).isoformat()
    batch["image_root"] = str(root)
    return downloaded, reused


def validate_image_batch(batch):
    if not isinstance(batch, dict) or batch.get("schema_version") != 1 or not isinstance(batch.get("products"), list):
        raise ValueError("Expected schema_version 1 extraction JSON with a products list.")
    for index, product in enumerate(batch["products"], 1):
        if not isinstance(product, dict) or not isinstance(product.get("source_url"), str):
            raise ValueError(f"Product {index} must include a source_url.")
        source_url(product["source_url"], "product")
        if not isinstance(product.get("images"), list):
            raise ValueError(f"Product {index} must include an images list.")
        if any(not isinstance(image, dict) or not isinstance(image.get("url"), str) for image in product["images"]):
            raise ValueError(f"Product {index} has an invalid image entry; each needs a url.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    extract = commands.add_parser("extract", help="Scrape supplied product URLs to review JSON; no image downloads.")
    extract.add_argument("urls", nargs="*", help="Direct HTTPS Smartlinks product URLs.")
    extract.add_argument(
        "--urls-file", type=Path,
        help="UTF-8 file with one URL per line; blank lines and # comments are ignored.",
    )
    images = commands.add_parser("images", help="Download gallery images separately; no database writes.")
    images.add_argument("--input", type=Path, required=True, help="Extraction JSON.")
    images.add_argument("--image-root", type=Path, required=True, help="Local directory for staged images.")
    for command in (extract, images):
        command.add_argument(
            "--output", type=Path, required=True, help="Output JSON; use a separate file for manual review.",
        )
        command.add_argument("--overwrite", action="store_true", help="Explicitly permit replacing the output JSON.")
        command.add_argument(
            "--delay", type=float, default=1.0,
            help="Minimum seconds between requests (at least 1; robots may require more).",
        )
    args = parser.parse_args(argv)
    if not args.delay >= 1 or not args.delay < float("inf"):
        parser.error("--delay must be a finite number of at least 1 second.")
    if args.output.exists() and not args.overwrite:
        parser.error("Output already exists; choose another file or pass --overwrite.")
    try:
        client = SmartlinksClient(delay=args.delay)
        if args.command == "extract":
            urls = list(args.urls)
            if args.urls_file:
                urls.extend(
                    line.strip() for line in args.urls_file.read_text(encoding="utf-8-sig").splitlines()
                    if line.strip() and not line.lstrip().startswith("#")
                )
                if args.output.resolve() == args.urls_file.resolve():
                    raise ValueError("The output must differ from the URL list.")
            if not urls:
                raise ValueError("Supply product URLs or --urls-file.")
            batch = extract_urls(urls, client)
            failed = len(batch["errors"])
            summary = f"Extracted {len(batch['products'])} products; {failed} errors."
        else:
            if args.input.resolve() == args.output.resolve():
                raise ValueError("Image output must differ from the input JSON to preserve your review file.")
            batch = json.loads(args.input.read_text(encoding="utf-8-sig"))
            validate_image_batch(batch)
            downloaded, reused = download_images(batch, client, args.image_root)
            failed = len(batch["image_errors"])
            summary = f"Downloaded {downloaded} images; reused {reused}; {failed} image errors."
        write_json(args.output, batch, overwrite=args.overwrite)
        print(f"{summary} Saved {args.output}")
        return 1 if failed else 0
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
