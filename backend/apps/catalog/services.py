from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from apps.audit.services import record_audit_event

from .models import Product


def validate_product_prices(*, regular_price, sale_price):
    errors = {}
    if regular_price is not None and regular_price < 0:
        errors["regular_price"] = ["Regular price cannot be negative."]
    if sale_price is not None:
        if sale_price < 0:
            errors["sale_price"] = ["Sale price cannot be negative."]
        elif regular_price is not None and sale_price >= regular_price:
            errors["sale_price"] = ["Sale price must be lower than regular price."]
    if errors:
        raise ValidationError(errors)


def save_taxonomy(*, instance, data):
    """Save validated taxonomy fields, including explicit activation changes."""
    for field, value in data.items():
        setattr(instance, field, value)
    try:
        with transaction.atomic():
            if instance.pk:
                instance.save(update_fields=[*data, "updated_at"])
            else:
                instance.save()
    except IntegrityError:
        # Serializer uniqueness checks alone cannot prevent simultaneous duplicates.
        duplicates = {}
        for field in ("name", "slug"):
            if type(instance).objects.exclude(pk=instance.pk).filter(**{field: getattr(instance, field)}).exists():
                duplicates[field] = [f"An entry with this {field} already exists."]
        if duplicates:
            raise ValidationError(duplicates) from None
        raise
    return instance


def _identifier_errors(instance):
    errors = {}
    for field in ("sku", "slug"):
        value = getattr(instance, field)
        if Product.objects.exclude(pk=instance.pk).filter(**{f"{field}__iexact": value}).exists():
            errors[field] = [f"A product with this {field} already exists."]
    return errors


@transaction.atomic
def create_product_draft(*, data):
    product = Product(**data, stock_quantity=0, is_published=False)
    validate_product_prices(regular_price=product.regular_price, sale_price=product.sale_price)
    try:
        with transaction.atomic():
            product.save()
    except IntegrityError:
        if errors := _identifier_errors(product):
            raise ValidationError(errors) from None
        raise
    return product


@transaction.atomic
def update_product_draft(*, product, data, actor):
    locked = Product.objects.select_for_update().get(pk=product.pk)
    before_price = {
        "regular_price": str(locked.regular_price),
        "sale_price": str(locked.sale_price) if locked.sale_price is not None else None,
    }
    for field, value in data.items():
        setattr(locked, field, value)
    validate_product_prices(regular_price=locked.regular_price, sale_price=locked.sale_price)
    try:
        with transaction.atomic():
            locked.save(update_fields=[*data, "updated_at"])
    except IntegrityError:
        if errors := _identifier_errors(locked):
            raise ValidationError(errors) from None
        raise

    after_price = {
        "regular_price": str(locked.regular_price),
        "sale_price": str(locked.sale_price) if locked.sale_price is not None else None,
    }
    if before_price != after_price:
        record_audit_event(
            actor=actor,
            resource_type="Product",
            resource_id=locked.pk,
            action="PRODUCT_PRICE_CHANGED",
            before_data=before_price,
            after_data=after_price,
        )
    return locked
