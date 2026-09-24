from rest_framework import serializers

from apps.catalog.models import Brand, Category, Product
from apps.catalog.services import create_product_draft, save_taxonomy, update_product_draft, validate_product_prices


class TaxonomySerializer(serializers.ModelSerializer):
    class Meta:
        fields = ("id", "name", "slug", "description", "is_active", "sort_order", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def create(self, validated_data):
        return save_taxonomy(instance=self.Meta.model(), data=validated_data)

    def update(self, instance, validated_data):
        return save_taxonomy(instance=instance, data=validated_data)


class BrandSerializer(TaxonomySerializer):
    class Meta(TaxonomySerializer.Meta):
        model = Brand


class CategorySerializer(TaxonomySerializer):
    class Meta(TaxonomySerializer.Meta):
        model = Category


class ProductDraftSerializer(serializers.ModelSerializer):
    selling_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Product
        fields = (
            "id", "brand", "category", "sku", "slug", "name", "short_description", "full_description",
            "regular_price", "sale_price", "selling_price", "warranty_text", "stock_quantity", "is_published",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "selling_price", "stock_quantity", "is_published", "created_at", "updated_at")

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
        for field in ("stock_quantity", "is_published"):
            if field in self.initial_data:
                forbidden[field] = ["This field cannot be changed through the product draft API."]
        if forbidden:
            raise serializers.ValidationError(forbidden)

        regular_price = attrs.get("regular_price", getattr(self.instance, "regular_price", None))
        sale_price = attrs.get("sale_price", getattr(self.instance, "sale_price", None))
        validate_product_prices(regular_price=regular_price, sale_price=sale_price)
        return attrs

    def create(self, validated_data):
        return create_product_draft(data=validated_data)

    def update(self, instance, validated_data):
        return update_product_draft(
            product=instance,
            data=validated_data,
            actor=self.context["request"].user,
        )
