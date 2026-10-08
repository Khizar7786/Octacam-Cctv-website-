import uuid

from django.conf import settings
from django.db import transaction

from .image_services import prepare_image
from .models import Brand
from .services import save_taxonomy


def save_brand(*, instance, data):
    """Save brand fields and its optional logo without deleting files before commit."""
    data = dict(data)
    logo_supplied = "logo" in data
    upload = data.pop("logo", None)
    remove_logo = data.pop("remove_logo", False)
    prepared = (
        prepare_image(upload, max_bytes=settings.BRAND_LOGO_MAX_BYTES, error_field="logo")
        if upload is not None else None
    )

    new_key = None
    storage = instance.logo.storage
    try:
        with transaction.atomic():
            if instance.pk:
                instance = Brand.objects.select_for_update().get(pk=instance.pk)
            old_key = instance.logo.name
            if prepared is not None:
                content, extension, _, _ = prepared
                new_key = storage.save(f"brands/{uuid.uuid4().hex}.{extension}", content)
                data["logo"] = new_key
            elif logo_supplied or remove_logo:
                data["logo"] = ""

            instance = save_taxonomy(instance=instance, data=data)
            if old_key and old_key != instance.logo.name:
                transaction.on_commit(lambda: storage.delete(old_key), robust=True)
    except Exception:
        # Files are not transactional: discard this upload if its database write fails.
        if new_key is not None:
            storage.delete(new_key)
        raise
    return instance
