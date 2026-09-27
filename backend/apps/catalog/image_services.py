import io
import uuid
import warnings

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Max
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework.exceptions import ValidationError

from .models import Product, ProductImage


IMAGE_FORMATS = {
    "JPEG": ("image/jpeg", "jpg"),
    "PNG": ("image/png", "png"),
    "WEBP": ("image/webp", "webp"),
}


def prepare_product_image(upload):
    if upload.content_type not in {mime for mime, _ in IMAGE_FORMATS.values()}:
        raise ValidationError({"image": ["Upload a JPEG, PNG, or WebP image."]})
    if upload.size > settings.PRODUCT_IMAGE_MAX_BYTES:
        raise ValidationError({"image": ["The image exceeds the 5 MB upload limit."]})

    try:
        content = upload.read()
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as probe:
                image_format = probe.format
                if image_format not in IMAGE_FORMATS:
                    raise ValueError("Unsupported image format")
                if upload.content_type != IMAGE_FORMATS[image_format][0]:
                    raise ValueError("Content type does not match the image")
                width, height = probe.size
                if (
                    width > settings.PRODUCT_IMAGE_MAX_WIDTH
                    or height > settings.PRODUCT_IMAGE_MAX_HEIGHT
                    or width * height > settings.PRODUCT_IMAGE_MAX_PIXELS
                    or getattr(probe, "n_frames", 1) != 1
                ):
                    raise ValueError("Image dimensions are too large or the image is animated")
                probe.verify()

            with Image.open(io.BytesIO(content)) as decoded:
                decoded.load()
                normalized = ImageOps.exif_transpose(decoded)
                if image_format == "JPEG":
                    normalized = normalized.convert("RGB")
                else:
                    has_alpha = "A" in normalized.getbands() or "transparency" in normalized.info
                    normalized = normalized.convert("RGBA" if has_alpha else "RGB")
                width, height = normalized.size
                output = io.BytesIO()
                save_options = {"quality": 85} if image_format == "JPEG" else {}
                normalized.save(output, format=image_format, **save_options)
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombWarning,
            Image.DecompressionBombError):
        raise ValidationError({"image": ["The file is not a safe, decodable image of the declared type."]}) from None

    if output.tell() > settings.PRODUCT_IMAGE_MAX_BYTES:
        raise ValidationError({"image": ["The normalized image exceeds the 5 MB limit."]})
    extension = IMAGE_FORMATS[image_format][1]
    return ContentFile(output.getvalue()), extension, width, height


def _store_image(*, product_id, content, extension):
    key = f"products/{product_id}/{uuid.uuid4().hex}.{extension}"
    return default_storage.save(key, content)


@transaction.atomic
def create_product_image(*, product, upload, alt_text, sort_order=None):
    content, extension, width, height = prepare_product_image(upload)
    Product.objects.select_for_update().get(pk=product.pk)
    if sort_order is None:
        current_max = ProductImage.objects.filter(product_id=product.pk).aggregate(value=Max("sort_order"))["value"]
        sort_order = 0 if current_max is None else current_max + 1
    elif ProductImage.objects.filter(product_id=product.pk, sort_order=sort_order).exists():
        raise ValidationError({"sort_order": ["This order is already used by another product image."]})

    key = _store_image(product_id=product.pk, content=content, extension=extension)
    try:
        return ProductImage.objects.create(
            product_id=product.pk,
            image=key,
            alt_text=alt_text,
            sort_order=sort_order,
            width=width,
            height=height,
        )
    except Exception:
        default_storage.delete(key)
        raise


@transaction.atomic
def update_product_image(*, product_image, data):
    upload = data.pop("image", None)
    prepared = prepare_product_image(upload) if upload is not None else None
    Product.objects.select_for_update().get(pk=product_image.product_id)
    locked = ProductImage.objects.select_for_update().get(pk=product_image.pk)
    old_key = locked.image.name
    new_key = None
    try:
        new_order = data.get("sort_order", locked.sort_order)
        if new_order != locked.sort_order:
            occupant = ProductImage.objects.filter(product_id=locked.product_id, sort_order=new_order).first()
            if occupant is not None:
                current_max = ProductImage.objects.filter(product_id=locked.product_id).aggregate(
                    value=Max("sort_order")
                )["value"]
                if current_max >= 2_147_483_647:
                    raise ValidationError({"sort_order": ["Cannot reorder images at the maximum order value."]})
                occupant.sort_order = current_max + 1
                occupant.save(update_fields=["sort_order"])
            previous_order = locked.sort_order
            locked.sort_order = new_order
            locked.save(update_fields=["sort_order"])
            if occupant is not None:
                occupant.sort_order = previous_order
                occupant.save(update_fields=["sort_order"])

        fields = []
        if "alt_text" in data:
            locked.alt_text = data["alt_text"]
            fields.append("alt_text")
        if prepared is not None:
            content, extension, locked.width, locked.height = prepared
            new_key = _store_image(product_id=locked.product_id, content=content, extension=extension)
            locked.image = new_key
            fields.extend(("image", "width", "height"))
        if fields:
            locked.save(update_fields=fields)
    except Exception:
        if new_key is not None:
            default_storage.delete(new_key)
        raise

    if new_key is not None:
        transaction.on_commit(lambda: default_storage.delete(old_key), robust=True)
    return locked


@transaction.atomic
def delete_product_image(*, product_image):
    Product.objects.select_for_update().get(pk=product_image.product_id)
    locked = ProductImage.objects.select_for_update().get(pk=product_image.pk)
    key = locked.image.name
    locked.delete()
    transaction.on_commit(lambda: default_storage.delete(key), robust=True)
