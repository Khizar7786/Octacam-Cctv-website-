from rest_framework import serializers

from apps.catalog.brand_services import save_brand
from apps.catalog.models import Brand, Category, InventoryMovement, Product, ProductImage, SpecificationChoice, SpecificationDefinition
from apps.catalog.services import (
    create_product_draft,
    save_specification_choice,
    save_specification_definition,
    save_taxonomy,
    update_product,
    validate_product_prices,
)


class TaxonomySerializer(serializers.ModelSerializer):
    class Meta:
        fields = ("id", "name", "slug", "description", "is_active", "sort_order", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def create(self, validated_data):
        return save_taxonomy(instance=self.Meta.model(), data=validated_data)

    def update(self, instance, validated_data):
        return save_taxonomy(instance=instance, data=validated_data)


class BrandSerializer(TaxonomySerializer):
    # Multipart omission must preserve the same creation default as JSON.
    is_active = serializers.BooleanField(required=False, default=True)
    logo = serializers.FileField(
        required=False, allow_null=True, write_only=True,
        help_text="PNG, JPEG, or WebP logo up to 2 MB. Send null in JSON to remove it.",
    )
    remove_logo = serializers.BooleanField(
        required=False, write_only=True,
        help_text="Send true to remove the current logo, including in multipart requests.",
    )
    logo_url = serializers.SerializerMethodField()

    class Meta(TaxonomySerializer.Meta):
        model = Brand
        fields = (*TaxonomySerializer.Meta.fields, "logo", "remove_logo", "logo_url")

    def get_logo_url(self, obj) -> str | None:
        return obj.logo.url if obj.logo else None

    def validate(self, attrs):
        if attrs.get("remove_logo") and attrs.get("logo") is not None:
            raise serializers.ValidationError({"logo": ["Upload a logo or remove it, not both."]})
        return attrs

    def create(self, validated_data):
        return save_brand(instance=Brand(), data=validated_data)

    def update(self, instance, validated_data):
        return save_brand(instance=instance, data=validated_data)


class CategorySerializer(TaxonomySerializer):
    class Meta(TaxonomySerializer.Meta):
        model = Category


class SpecificationChoiceSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = SpecificationChoice
        fields = ("id", "value", "label", "is_active", "sort_order")


class SpecificationDefinitionSerializer(serializers.ModelSerializer):
    choices = SpecificationChoiceSummarySerializer(many=True, read_only=True)

    class Meta:
        model = SpecificationDefinition
        fields = (
            "id", "category", "key", "label", "data_type", "unit", "is_required", "is_filterable",
            "is_displayed", "is_active", "sort_order", "choices", "created_at", "updated_at",
        )
        read_only_fields = ("id", "category", "created_at", "updated_at")

    def validate_key(self, value):
        value = value.strip().lower()
        category = self.instance.category if self.instance else self.context["category"]
        queryset = SpecificationDefinition.objects.filter(category=category, key=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("This category already has a specification with this key.")
        return value

    def create(self, validated_data):
        return save_specification_definition(
            instance=SpecificationDefinition(),
            category=self.context["category"],
            data=validated_data,
        )

    def update(self, instance, validated_data):
        return save_specification_definition(instance=instance, category=instance.category, data=validated_data)


class SpecificationChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpecificationChoice
        fields = ("id", "definition", "value", "label", "is_active", "sort_order")
        read_only_fields = ("id", "definition")

    def validate_value(self, value):
        value = value.strip().lower()
        definition = self.instance.definition if self.instance else self.context["definition"]
        queryset = SpecificationChoice.objects.filter(definition=definition, value=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("This specification already has a choice with this value.")
        return value

    def create(self, validated_data):
        return save_specification_choice(
            instance=SpecificationChoice(),
            definition=self.context["definition"],
            data=validated_data,
        )

    def update(self, instance, validated_data):
        return save_specification_choice(instance=instance, definition=instance.definition, data=validated_data)


def specification_value_data(value):
    definition = value.definition
    if definition.data_type == SpecificationDefinition.DataType.TEXT:
        raw_value = value.text_value
        display_value = raw_value
    elif definition.data_type == SpecificationDefinition.DataType.INTEGER:
        raw_value = value.integer_value
        display_value = str(raw_value)
    elif definition.data_type == SpecificationDefinition.DataType.DECIMAL:
        raw_value = format(value.decimal_value, "f")
        display_value = raw_value
    elif definition.data_type == SpecificationDefinition.DataType.BOOLEAN:
        raw_value = value.boolean_value
        display_value = "Yes" if raw_value else "No"
    else:
        raw_value = value.choice.value
        display_value = value.choice.label
    if definition.unit and definition.data_type != SpecificationDefinition.DataType.BOOLEAN:
        display_value = f"{display_value} {definition.unit}"
    return {
        "definition": definition.id,
        "key": definition.key,
        "label": definition.label,
        "data_type": definition.data_type,
        "unit": definition.unit,
        "value": raw_value,
        "display_value": display_value,
    }


class ProductSpecificationsField(serializers.ListField):
    child = serializers.JSONField()

    def get_attribute(self, instance):
        return instance

    def to_representation(self, product):
        return [specification_value_data(value) for value in product.specification_values.all()]

    def to_internal_value(self, data):
        entries = super().to_internal_value(data)
        for entry in entries:
            if not isinstance(entry, dict):
                raise serializers.ValidationError("Each specification must be an object.")
            unknown = set(entry) - {"definition", "value"}
            if unknown:
                raise serializers.ValidationError(
                    f"Unknown specification fields: {', '.join(sorted(unknown))}."
                )
            if "definition" not in entry or "value" not in entry:
                raise serializers.ValidationError("Each specification requires definition and value.")
        return entries


class ProductImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ("id", "image_url", "alt_text", "sort_order", "width", "height", "created_at")

    def get_image_url(self, obj) -> str:
        return obj.image.url


class ProductImageWriteSerializer(serializers.Serializer):
    image = serializers.FileField()
    alt_text = serializers.CharField(max_length=255, trim_whitespace=True)
    sort_order = serializers.IntegerField(required=False, min_value=0, max_value=2_147_483_647)


class StockAdjustmentWriteSerializer(serializers.Serializer):
    new_quantity = serializers.IntegerField(min_value=0, max_value=2_147_483_647)
    reason = serializers.CharField(max_length=500, trim_whitespace=True, allow_blank=False)


class InventoryMovementSerializer(serializers.ModelSerializer):
    movement_type = serializers.CharField(source="reason", read_only=True)
    reason = serializers.CharField(source="note", read_only=True)

    class Meta:
        model = InventoryMovement
        fields = (
            "id", "product", "previous_quantity", "new_quantity", "quantity_delta",
            "movement_type", "reason", "actor", "created_at",
        )
        read_only_fields = fields


class ProductStaffSerializer(serializers.ModelSerializer):
    selling_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    specifications = ProductSpecificationsField(required=False)
    images = ProductImageSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = (
            "id", "brand", "category", "sku", "slug", "name", "short_description", "full_description",
            "regular_price", "sale_price", "selling_price", "warranty_text", "stock_quantity", "is_published",
            "specifications", "images", "created_at", "updated_at",
        )
        read_only_fields = ("id", "selling_price", "stock_quantity", "created_at", "updated_at")

    def validate_sku(self, value):
        value = value.strip().upper()
        queryset = Product.objects.filter(sku__iexact=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("A product with this sku already exists.")
        return value

    def validate_slug(self, value):
        value = value.lower()
        queryset = Product.objects.filter(slug__iexact=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("A product with this slug already exists.")
        return value

    def validate(self, attrs):
        forbidden = {}
        if "stock_quantity" in self.initial_data:
            forbidden["stock_quantity"] = ["Stock must be changed through the inventory workflow."]
        if self.instance is None and "is_published" in self.initial_data:
            forbidden["is_published"] = ["Create the draft first, then publish it with PATCH after validation."]
        if forbidden:
            raise serializers.ValidationError(forbidden)

        regular_price = attrs.get("regular_price", getattr(self.instance, "regular_price", None))
        sale_price = attrs.get("sale_price", getattr(self.instance, "sale_price", None))
        validate_product_prices(regular_price=regular_price, sale_price=sale_price)
        return attrs

    def create(self, validated_data):
        return create_product_draft(data=validated_data)

    def update(self, instance, validated_data):
        return update_product(
            product=instance,
            data=validated_data,
            actor=self.context["request"].user,
        )


class TaxonomySummarySerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    slug = serializers.SlugField(read_only=True)


class PublicProductListSerializer(serializers.ModelSerializer):
    brand = TaxonomySummarySerializer(read_only=True)
    category = TaxonomySummarySerializer(read_only=True)
    selling_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    is_in_stock = serializers.SerializerMethodField()
    primary_image = ProductImageSerializer(read_only=True, allow_null=True)
    secondary_image = ProductImageSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Product
        fields = (
            "id", "brand", "category", "sku", "slug", "name", "short_description", "regular_price",
            "sale_price", "selling_price", "stock_quantity", "is_in_stock", "primary_image", "secondary_image",
        )

    def get_is_in_stock(self, obj) -> bool:
        return obj.stock_quantity > 0

class PublicProductDetailSerializer(PublicProductListSerializer):
    specifications = ProductSpecificationsField(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)

    class Meta(PublicProductListSerializer.Meta):
        fields = PublicProductListSerializer.Meta.fields + (
            "full_description", "warranty_text", "specifications", "images", "updated_at",
        )


class FilterOptionSerializer(serializers.Serializer):
    value = serializers.SlugField()
    label = serializers.CharField()


class PriceBoundsSerializer(serializers.Serializer):
    min = serializers.CharField(allow_null=True)
    max = serializers.CharField(allow_null=True)


class SpecificationFilterSerializer(serializers.Serializer):
    key = serializers.SlugField()
    label = serializers.CharField()
    type = serializers.ChoiceField(choices=("choice", "boolean", "integer_range", "decimal_range"))
    unit = serializers.CharField()
    options = serializers.JSONField(required=False)
    min = serializers.CharField(required=False, allow_null=True)
    max = serializers.CharField(required=False, allow_null=True)


class PublicFilterMetadataSerializer(serializers.Serializer):
    brand = FilterOptionSerializer(many=True)
    category = FilterOptionSerializer(many=True)
    price = PriceBoundsSerializer()
    specifications = SpecificationFilterSerializer(many=True)
