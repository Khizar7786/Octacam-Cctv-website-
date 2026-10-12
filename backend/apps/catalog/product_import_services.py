"""Import reviewed catalog data as drafts without changing existing products."""

import logging
from contextlib import nullcontext
from pathlib import Path, PureWindowsPath

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.validators import URLValidator
from django.db import IntegrityError, transaction
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.services import record_audit_event

from .brand_services import save_brand
from .image_services import create_product_image, prepare_product_image
from .models import Brand, Category, Product, SpecificationChoice, SpecificationDefinition
from .services import create_product_draft, save_specification_choice, save_specification_definition, save_taxonomy


logger = logging.getLogger(__name__)
IMAGE_CONTENT_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError({field: ["Provide a non-empty string."]})
    return value.strip()


def _clean(instance):
    try:
        instance.full_clean()
    except DjangoValidationError as exc:
        raise ValidationError(exc.message_dict) from exc
    return instance


def _taxonomy(model, reference, field):
    if isinstance(reference, str):
        reference = _text(reference, field)
        matches = list(model.objects.filter(Q(slug__iexact=reference) | Q(name__iexact=reference)))
    elif isinstance(reference, dict):
        unknown = set(reference) - {"name", "slug", "create"}
        if unknown:
            raise ValidationError({field: [f"Unknown fields: {', '.join(sorted(unknown))}."]})
        name = _text(reference.get("name"), f"{field}.name")
        slug = _text(reference.get("slug"), f"{field}.slug").lower()
        matches = list(model.objects.filter(Q(slug__iexact=slug) | Q(name__iexact=name)))
        if matches and any(match.slug.lower() != slug or match.name.casefold() != name.casefold() for match in matches):
            raise ValidationError({field: ["Name and slug conflict with existing entries; select one existing entry."]})
    else:
        raise ValidationError({field: ["Select an existing name/slug, or provide name, slug, and create: true."]})
    if len(matches) > 1:
        raise ValidationError({field: ["The reference is ambiguous; use the exact existing slug."]})
    if matches:
        if not matches[0].is_active:
            raise ValidationError({field: ["The selected entry is inactive; resolve it through the staff API."]})
        return matches[0]
    if not isinstance(reference, dict) or reference.get("create") is not True:
        raise ValidationError({field: ["Entry not found. Creating one requires name, slug, and create: true."]})
    instance = _clean(model(name=name, slug=slug))
    save = save_brand if model is Brand else save_taxonomy
    return save(instance=instance, data={"name": instance.name, "slug": instance.slug})


def _specifications(category, entries):
    if not isinstance(entries, list):
        raise ValidationError({"specifications": ["Provide a list of reviewed specifications."]})
    prepared = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValidationError({"specifications": ["Each specification must be an object."]})
        unknown = set(entry) - {"key", "label", "data_type", "unit", "create", "value", "create_choice", "choice_label", "source_section"}
        if unknown:
            raise ValidationError({"specifications": [f"Unknown fields: {', '.join(sorted(unknown))}."]})
        key = _text(entry.get("key"), "specifications.key").lower()
        if key in seen:
            raise ValidationError({"specifications": [f"Repeated key: {key}."]})
        seen.add(key)
        if "value" not in entry:
            raise ValidationError({"specifications": [f"Provide a value for {key}."]})
        definition = SpecificationDefinition.objects.filter(category=category, key=key).first()
        if definition:
            if not definition.is_active:
                raise ValidationError({"specifications": [f"{key} is inactive."]})
            for field in ("data_type", "unit"):
                if field in entry and entry[field] != getattr(definition, field):
                    raise ValidationError({"specifications": [f"{key}: {field} conflicts with the existing definition."]})
        else:
            if entry.get("create") is not True:
                raise ValidationError({"specifications": [f"{key} does not exist; provide create: true, label, and data_type."]})
            definition = _clean(SpecificationDefinition(
                category=category, key=key, label=_text(entry.get("label"), "specifications.label"),
                data_type=_text(entry.get("data_type"), "specifications.data_type"), unit=entry.get("unit", ""),
            ))
            definition = save_specification_definition(
                instance=definition, category=category,
                data={"key": definition.key, "label": definition.label, "data_type": definition.data_type, "unit": definition.unit},
            )
        value = entry["value"]
        if definition.data_type == SpecificationDefinition.DataType.CHOICE:
            value = _text(value, f"specifications.{key}.value").lower()
            choice = definition.choices.filter(value=value).first()
            if choice is None and entry.get("create_choice") is True:
                choice = _clean(SpecificationChoice(
                    definition=definition, value=value,
                    label=_text(entry.get("choice_label"), "specifications.choice_label"),
                ))
                save_specification_choice(
                    instance=choice, definition=definition, data={"value": choice.value, "label": choice.label},
                )
        elif "create_choice" in entry or "choice_label" in entry:
            raise ValidationError({"specifications": [f"{key} is not a choice specification."]})
        prepared.append({"definition": definition.pk, "value": value})
    return prepared


def _images(entries, root):
    if not isinstance(entries, list):
        raise ValidationError({"images": ["Provide an ordered images list."]})
    uploads = []
    seen = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValidationError({"images": ["Each image must be an object."]})
        relative = entry.get("local_path")
        if relative is None:
            continue  # Remote references are never fetched by an importer.
        relative = _text(relative, "images.local_path")
        if root is None:
            raise ValidationError({"images": ["Local images require an explicit --image-root."]})
        windows_path = PureWindowsPath(relative)
        if Path(relative).is_absolute() or windows_path.drive or ".." in windows_path.parts:
            raise ValidationError({"images": ["Use relative paths inside --image-root; parent traversal is forbidden."]})
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValidationError({"images": [f"Image is missing or outside --image-root: {relative}."]})
        if path in seen:
            raise ValidationError({"images": [f"Repeated local image: {relative}."]})
        seen.add(path)
        content_type = IMAGE_CONTENT_TYPES.get(path.suffix.lower())
        if content_type is None:
            raise ValidationError({"images": ["Local images must be JPEG, PNG, or WebP."]})
        # Bound the read as well as checking stat, in case the file changes during import.
        with path.open("rb") as handle:
            body = handle.read(settings.PRODUCT_IMAGE_MAX_BYTES + 1)
        upload = SimpleUploadedFile(path.name, body, content_type=content_type)
        prepare_product_image(upload)
        upload.seek(0)
        alt_text = _text(entry.get("alt_text"), "images.alt_text")
        if len(alt_text) > 255:
            raise ValidationError({"images.alt_text": ["Use at most 255 characters."]})
        uploads.append((upload, alt_text, index))
    return uploads


def _review(row):
    if not isinstance(row, dict):
        raise ValidationError({"product": ["Each product must be an object."]})
    for flag in ("reviewed", "pricing_approved"):
        if row.get(flag) is not True:
            raise ValidationError({flag: ["Explicit approval must be the JSON boolean true."]})
    if row.get("currency") != "PKR":
        raise ValidationError({"currency": ["Approve prices explicitly in PKR."]})
    if row.get("is_published", False) is not False:
        raise ValidationError({"is_published": ["Imports create drafts only; publish separately."]})
    quantity = row.get("stock_quantity", 0)
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity != 0:
        raise ValidationError({"stock_quantity": ["Imports start at zero; verify stock through the inventory workflow."]})
    sku = _text(row.get("sku"), "sku").upper()
    if len(sku) > 120:
        raise ValidationError({"sku": ["Use at most 120 characters."]})
    return sku


def _import_row(row, *, actor, root, dry_run, metadata):
    stored = []
    try:
        # Real imports own their commit: callers cannot later roll back referenced files.
        with transaction.atomic(durable=not dry_run):
            sku = _review(row)
            existing = Product.objects.filter(sku__iexact=sku).first()
            if existing:
                return {
                    "status": "skipped", "sku": sku, "product_id": None if dry_run else existing.pk,
                    "reason": "SKU already exists.",
                }
            source_url = _text(row.get("source_url"), "source_url")
            try:
                URLValidator(schemes=["https"])(source_url)
            except DjangoValidationError as exc:
                raise ValidationError({"source_url": exc.messages}) from exc
            brand = _taxonomy(Brand, row.get("brand"), "brand")
            category = _taxonomy(Category, row.get("category"), "category")
            regular = _text(row.get("regular_price"), "regular_price")
            sale = row.get("sale_price")
            if sale is not None:
                sale = _text(sale, "sale_price")
            warranty = row.get("warranty_text")
            if warranty is not None and not isinstance(warranty, str):
                raise ValidationError({"warranty_text": ["Provide approved text or null."]})
            candidate = _clean(Product(
                brand=brand, category=category, sku=sku,
                slug=_text(row.get("slug"), "slug").lower(), name=_text(row.get("name"), "name"),
                short_description=_text(row.get("short_description"), "short_description"),
                full_description=_text(row.get("full_description"), "full_description"),
                regular_price=regular, sale_price=sale, warranty_text=(warranty or "").strip(),
            ))
            specifications = _specifications(category, row.get("specifications", []))
            uploads = _images(row.get("images", []), root)
            product = create_product_draft(data={
                field: getattr(candidate, field) for field in (
                    "brand", "category", "sku", "slug", "name", "short_description", "full_description",
                    "regular_price", "sale_price", "warranty_text",
                )
            } | {"specifications": specifications})
            if not dry_run:
                for upload, alt_text, sort_order in uploads:
                    image = create_product_image(product=product, upload=upload, alt_text=alt_text, sort_order=sort_order)
                    stored.append((image.image.storage, image.image.name))
                record_audit_event(
                    actor=actor, resource_type="Product", resource_id=product.pk, action="PRODUCT_IMPORTED",
                    before_data={},
                    after_data={
                        "sku": product.sku, "regular_price": str(product.regular_price),
                        "sale_price": str(product.sale_price) if product.sale_price is not None else None,
                        "brand_id": brand.pk, "category_id": category.pk, "stock_quantity": 0,
                        "is_published": False, "image_count": len(uploads),
                    },
                    metadata={**metadata, "source_url": source_url, "source_sha256": row.get("source_sha256"),
                              "reviewed": True, "pricing_approved": True},
                )
            return {
                "status": "validated" if dry_run else "created", "sku": sku,
                "product_id": None if dry_run else product.pk, "image_count": len(uploads),
                "remote_images_skipped": len(row.get("images", [])) - len(uploads),
            }
    except BaseException:
        for storage, key in stored:
            try:
                storage.delete(key)
            except Exception:
                logger.exception("Could not clean up rolled-back import image %s", key)
        raise


def import_reviewed_products(*, batch, actor, image_root=None, dry_run=False, metadata=None):
    """Import independent rows, or validate the batch in a rolled-back simulation."""
    if not actor or not actor.is_authenticated or not actor.is_active or not actor.is_staff:
        raise PermissionDenied("An active authenticated staff actor is required.")
    if (
        not isinstance(batch, dict) or type(batch.get("schema_version")) is not int
        or batch["schema_version"] != 1 or not isinstance(batch.get("products"), list)
    ):
        raise ValidationError({"input": ["Expected schema_version 1 JSON with a products list."]})
    root = Path(image_root).resolve() if image_root is not None else None
    if root is not None and not root.is_dir():
        raise ValidationError({"image_root": ["Provide an existing image directory."]})
    report = {"dry_run": dry_run, "counts": {"created": 0, "validated": 0, "skipped": 0, "error": 0}, "rows": []}
    provenance = {"extracted_at": batch.get("extracted_at"), **(metadata or {})}
    with transaction.atomic() if dry_run else nullcontext():
        for index, row in enumerate(batch["products"], 1):
            try:
                result = _import_row(row, actor=actor, root=root, dry_run=dry_run, metadata=provenance)
            except Exception as exc:
                sku = row.get("sku", "").strip().upper() if isinstance(row, dict) and isinstance(row.get("sku"), str) else ""
                existing = None
                if sku and isinstance(exc, (ValidationError, IntegrityError)):
                    try:
                        _review(row)
                    except ValidationError:
                        pass
                    else:
                        # A competing importer may have committed this SKU after our initial check.
                        existing = Product.objects.filter(sku__iexact=sku).first()
                if existing:
                    result = {
                        "status": "skipped", "sku": sku, "product_id": None if dry_run else existing.pk,
                        "reason": "SKU already exists.",
                    }
                else:
                    errors = exc.detail if isinstance(exc, ValidationError) else {"product": [str(exc)]}
                    result = {"status": "error", "sku": sku or None, "errors": errors}
                    logger.error("Product import row %s failed: %s", index, errors)
            result["row"] = index
            report["counts"][result["status"]] += 1
            report["rows"].append(result)
        if dry_run:
            transaction.set_rollback(True)
    return report
