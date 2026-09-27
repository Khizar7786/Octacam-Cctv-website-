from decimal import Decimal

from rest_framework import serializers

from apps.catalog.models import SpecificationChoice, SpecificationDefinition


class ProductDiscoveryQuerySerializer(serializers.Serializer):
    q = serializers.CharField(required=False, max_length=120, trim_whitespace=True)
    brand = serializers.SlugField(required=False, max_length=120)
    category = serializers.SlugField(required=False, max_length=120)
    min_price = serializers.DecimalField(required=False, max_digits=12, decimal_places=2, min_value=Decimal("0"))
    max_price = serializers.DecimalField(required=False, max_digits=12, decimal_places=2, min_value=Decimal("0"))
    availability = serializers.ChoiceField(required=False, choices=("in_stock", "out_of_stock"))
    sort = serializers.ChoiceField(required=False, choices=("relevance", "price_asc", "price_desc"))

    def validate(self, attrs):
        if attrs.get("min_price") is not None and attrs.get("max_price") is not None:
            if attrs["min_price"] > attrs["max_price"]:
                raise serializers.ValidationError({"max_price": "Must be at least min_price."})
        return attrs


def parse_discovery_query(params, *, metadata=False):
    allowed = {"brand", "category"} if metadata else set(ProductDiscoveryQuerySerializer().fields) | {"page"}
    errors = {}
    for key in params:
        if key not in allowed and not (not metadata and key.startswith("spec_")):
            errors[key] = ["Unknown filter parameter."]
        elif len(params.getlist(key)) != 1:
            errors[key] = ["Supply this parameter only once."]
    if errors:
        raise serializers.ValidationError(errors)

    basic = {key: params[key] for key in allowed - {"page"} if key in params}
    serializer = ProductDiscoveryQuerySerializer(data=basic, partial=True)
    serializer.is_valid(raise_exception=True)
    filters = serializer.validated_data
    definitions = {}
    if not metadata and any(key.startswith("spec_") for key in params):
        if not filters.get("category"):
            raise serializers.ValidationError({"category": "Select a category to use technical filters."})
        definitions = {
            definition.key: definition
            for definition in SpecificationDefinition.objects.filter(
                category__slug=filters["category"], category__is_active=True,
                is_active=True, is_filterable=True,
            )
        }
    specification_filters = []
    for key in params:
        if not key.startswith("spec_"):
            continue
        stem = key[5:]
        suffix = ""
        if stem not in definitions and (stem.endswith("_min") or stem.endswith("_max")):
            stem, suffix = stem.rsplit("_", 1)
        definition = definitions.get(stem)
        if definition is None or definition.data_type == SpecificationDefinition.DataType.TEXT:
            errors[key] = ["No active filterable specification for this category."]
            continue
        raw = params[key]
        if definition.data_type == SpecificationDefinition.DataType.CHOICE and not suffix:
            choice = SpecificationChoice.objects.filter(definition=definition, value=raw, is_active=True).first()
            if choice is None:
                errors[key] = ["Select an active choice."]
            else:
                specification_filters.append((definition, "choice_id", choice.pk))
        elif definition.data_type == SpecificationDefinition.DataType.BOOLEAN and not suffix:
            if raw not in {"true", "false"}:
                errors[key] = ["Use true or false."]
            else:
                specification_filters.append((definition, "boolean_value", raw == "true"))
        elif definition.data_type in {SpecificationDefinition.DataType.INTEGER, SpecificationDefinition.DataType.DECIMAL} and suffix:
            field = "integer_value" if definition.data_type == SpecificationDefinition.DataType.INTEGER else "decimal_value"
            value_serializer = (serializers.IntegerField if field == "integer_value" else serializers.DecimalField)
            parser = value_serializer() if field == "integer_value" else value_serializer(max_digits=18, decimal_places=4)
            try:
                value = parser.run_validation(raw)
            except serializers.ValidationError:
                errors[key] = ["Enter a valid number for this specification."]
            else:
                specification_filters.append((definition, f"{field}__{'gte' if suffix == 'min' else 'lte'}", value))
        else:
            errors[key] = ["This filter does not match the specification type."]
    for definition in definitions.values():
        minimum = next((value for item, lookup, value in specification_filters
                        if item.pk == definition.pk and lookup.endswith("__gte")), None)
        maximum = next((value for item, lookup, value in specification_filters
                        if item.pk == definition.pk and lookup.endswith("__lte")), None)
        if minimum is not None and maximum is not None and minimum > maximum:
            errors[f"spec_{definition.key}_max"] = ["Must be at least the minimum value."]
    if errors:
        raise serializers.ValidationError(errors)
    return filters, specification_filters
