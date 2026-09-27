from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import DecimalValidator
from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from apps.audit.services import record_audit_event

from .models import Product, ProductSpecificationValue, SpecificationChoice, SpecificationDefinition


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


def _definition_key_error(instance):
    duplicate = SpecificationDefinition.objects.exclude(pk=instance.pk).filter(
        category=instance.category,
        key=instance.key,
    ).exists()
    return {"key": ["This category already has a specification with this key."]} if duplicate else {}


@transaction.atomic
def save_specification_definition(*, instance, category, data):
    if "key" in data:
        data["key"] = data["key"].strip().lower()

    if instance.pk and "data_type" in data and data["data_type"] != instance.data_type:
        if instance.product_values.exists() or instance.choices.exists():
            raise ValidationError({
                "data_type": ["Data type cannot change after choices or product values have been added."],
            })

    candidate_active = data.get("is_active", instance.is_active if instance.pk else True)
    candidate_required = data.get("is_required", instance.is_required if instance.pk else False)
    if candidate_active and candidate_required:
        published = category.products.filter(is_published=True)
        if instance.pk:
            published = published.exclude(specification_values__definition=instance)
        if published.exists():
            raise ValidationError({
                "is_required": [
                    "Unpublish affected products or give them this value before making the specification required."
                ],
            })

    instance.category = category
    for field, value in data.items():
        setattr(instance, field, value)
    try:
        with transaction.atomic():
            if instance.pk:
                instance.save(update_fields=[*data, "updated_at"])
            else:
                instance.save()
    except IntegrityError:
        if errors := _definition_key_error(instance):
            raise ValidationError(errors) from None
        raise
    return instance


@transaction.atomic
def save_specification_choice(*, instance, definition, data):
    if definition.data_type != SpecificationDefinition.DataType.CHOICE:
        raise ValidationError({"definition": ["Choices can only be added to choice specifications."]})
    if "value" in data:
        data["value"] = data["value"].strip().lower()
    if instance.pk and instance.is_active and data.get("is_active") is False:
        if instance.product_values.filter(product__is_published=True).exists():
            raise ValidationError({
                "is_active": ["This choice is used by a published product. Change or unpublish it first."],
            })

    instance.definition = definition
    for field, value in data.items():
        setattr(instance, field, value)
    try:
        with transaction.atomic():
            instance.save()
    except IntegrityError:
        duplicate = SpecificationChoice.objects.exclude(pk=instance.pk).filter(
            definition=definition,
            value=instance.value,
        ).exists()
        if duplicate:
            raise ValidationError({"value": ["This specification already has a choice with this value."]}) from None
        raise
    return instance


def _decimal_specification_value(value):
    if isinstance(value, bool) or value is None:
        raise ValueError
    try:
        decimal_value = Decimal(str(value))
        DecimalValidator(max_digits=18, decimal_places=4)(decimal_value)
    except (InvalidOperation, DjangoValidationError, ValueError):
        raise ValueError from None
    if not decimal_value.is_finite():
        raise ValueError
    return decimal_value


def prepare_specification_values(*, category, entries):
    definition_ids = []
    for entry in entries:
        definition_id = entry.get("definition")
        if isinstance(definition_id, bool) or not isinstance(definition_id, int):
            raise ValidationError({"specifications": ["Each specification needs an integer definition ID."]})
        definition_ids.append(definition_id)
    if len(definition_ids) != len(set(definition_ids)):
        raise ValidationError({"specifications": ["Each specification definition may be supplied only once."]})

    definitions = {
        definition.id: definition
        for definition in SpecificationDefinition.objects.filter(id__in=definition_ids).prefetch_related("choices")
    }
    prepared = []
    for entry in entries:
        definition = definitions.get(entry["definition"])
        if definition is None:
            raise ValidationError({"specifications": [f"Definition {entry['definition']} does not exist."]})
        if definition.category_id != category.id:
            raise ValidationError({
                "specifications": [f"{definition.key} does not belong to the product category."],
            })
        if not definition.is_active:
            raise ValidationError({"specifications": [f"{definition.key} is inactive."]})

        value = entry.get("value")
        value_fields = {"definition": definition}
        if definition.data_type == SpecificationDefinition.DataType.TEXT:
            if not isinstance(value, str) or not value.strip():
                raise ValidationError({"specifications": [f"{definition.key} requires a non-empty text value."]})
            value_fields["text_value"] = value.strip()
        elif definition.data_type == SpecificationDefinition.DataType.INTEGER:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValidationError({"specifications": [f"{definition.key} requires an integer value."]})
            if not -(2**63) <= value < 2**63:
                raise ValidationError({"specifications": [f"{definition.key} is outside the supported integer range."]})
            value_fields["integer_value"] = value
        elif definition.data_type == SpecificationDefinition.DataType.DECIMAL:
            try:
                value_fields["decimal_value"] = _decimal_specification_value(value)
            except ValueError:
                raise ValidationError({
                    "specifications": [f"{definition.key} requires a decimal with at most four decimal places."],
                }) from None
        elif definition.data_type == SpecificationDefinition.DataType.BOOLEAN:
            if not isinstance(value, bool):
                raise ValidationError({"specifications": [f"{definition.key} requires a boolean value."]})
            value_fields["boolean_value"] = value
        else:
            if not isinstance(value, str):
                raise ValidationError({
                    "specifications": [f"{definition.key} requires an active choice value."],
                })
            choice = definition.choices.filter(value=value.strip().lower(), is_active=True).first()
            if choice is None:
                raise ValidationError({
                    "specifications": [f"{value} is not an active choice for {definition.key}."],
                })
            value_fields["choice"] = choice
        prepared.append(ProductSpecificationValue(**value_fields))
    return prepared


def _replace_specification_values(*, product, prepared):
    product.specification_values.all().delete()
    for value in prepared:
        value.product = product
    ProductSpecificationValue.objects.bulk_create(prepared)


def _stored_value_is_valid(value):
    definition = value.definition
    populated = {
        SpecificationDefinition.DataType.TEXT: value.text_value is not None and bool(value.text_value.strip()),
        SpecificationDefinition.DataType.INTEGER: value.integer_value is not None,
        SpecificationDefinition.DataType.DECIMAL: value.decimal_value is not None,
        SpecificationDefinition.DataType.BOOLEAN: value.boolean_value is not None,
        SpecificationDefinition.DataType.CHOICE: (
            value.choice_id is not None
            and value.choice.definition_id == definition.id
            and value.choice.is_active
        ),
    }
    return populated[definition.data_type]


def validate_product_for_publication(*, product):
    errors = []
    required_text = ("sku", "slug", "name", "short_description", "full_description")
    missing_text = [field for field in required_text if not str(getattr(product, field, "")).strip()]
    if missing_text:
        errors.append(f"Complete these product fields: {', '.join(missing_text)}.")
    if not product.brand.is_active:
        errors.append("The product brand must be active.")
    if not product.category.is_active:
        errors.append("The product category must be active.")
    validate_product_prices(regular_price=product.regular_price, sale_price=product.sale_price)

    required = list(product.category.specification_definitions.filter(is_active=True, is_required=True))
    values = {
        value.definition_id: value
        for value in product.specification_values.select_related("definition", "choice")
    }
    missing_specs = [
        definition.label
        for definition in required
        if definition.id not in values or not _stored_value_is_valid(values[definition.id])
    ]
    if missing_specs:
        errors.append(f"Complete required specifications: {', '.join(missing_specs)}.")
    if errors:
        raise ValidationError({"is_published": errors})


@transaction.atomic
def create_product_draft(*, data):
    specifications = data.pop("specifications", [])
    product = Product(**data, stock_quantity=0, is_published=False)
    validate_product_prices(regular_price=product.regular_price, sale_price=product.sale_price)
    prepared = prepare_specification_values(category=product.category, entries=specifications)
    try:
        with transaction.atomic():
            product.save()
    except IntegrityError:
        if errors := _identifier_errors(product):
            raise ValidationError(errors) from None
        raise
    _replace_specification_values(product=product, prepared=prepared)
    return product


@transaction.atomic
def update_product(*, product, data, actor):
    specifications_supplied = "specifications" in data
    specification_entries = data.pop("specifications", [])
    locked = Product.objects.select_for_update().select_related("brand", "category").get(pk=product.pk)
    before_price = {
        "regular_price": str(locked.regular_price),
        "sale_price": str(locked.sale_price) if locked.sale_price is not None else None,
    }
    before_publication = locked.is_published
    previous_category_id = locked.category_id
    for field, value in data.items():
        setattr(locked, field, value)

    if locked.category_id != previous_category_id and not specifications_supplied:
        if locked.specification_values.exists():
            raise ValidationError({
                "specifications": ["Supply the complete specification set when changing a product category."],
            })
    prepared = None
    if specifications_supplied:
        prepared = prepare_specification_values(category=locked.category, entries=specification_entries)

    validate_product_prices(regular_price=locked.regular_price, sale_price=locked.sale_price)
    try:
        with transaction.atomic():
            locked.save(update_fields=[*data, "updated_at"])
    except IntegrityError:
        if errors := _identifier_errors(locked):
            raise ValidationError(errors) from None
        raise

    if prepared is not None:
        _replace_specification_values(product=locked, prepared=prepared)
    if locked.is_published:
        validate_product_for_publication(product=locked)

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
    if before_publication != locked.is_published:
        record_audit_event(
            actor=actor,
            resource_type="Product",
            resource_id=locked.pk,
            action="PRODUCT_PUBLISHED" if locked.is_published else "PRODUCT_UNPUBLISHED",
            before_data={"is_published": before_publication},
            after_data={"is_published": locked.is_published},
        )
    return locked
