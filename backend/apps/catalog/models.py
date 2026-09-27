from django.db import models
from django.db.models.functions import Lower


class Taxonomy(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["sort_order", "name", "id"]

    def __str__(self):
        return self.name


class Brand(Taxonomy):
    pass


class Category(Taxonomy):
    class Meta(Taxonomy.Meta):
        abstract = False
        verbose_name_plural = "categories"


class Product(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name="products")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    sku = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=180, unique=True)
    name = models.CharField(max_length=255)
    short_description = models.CharField(max_length=500)
    full_description = models.TextField()
    regular_price = models.DecimalField(max_digits=12, decimal_places=2)
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    stock_quantity = models.PositiveIntegerField(default=0)
    warranty_text = models.TextField(blank=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(regular_price__gte=0), name="product_regular_price_gte_0"),
            models.CheckConstraint(
                condition=(
                    models.Q(sale_price__isnull=True)
                    | (models.Q(sale_price__gte=0) & models.Q(sale_price__lt=models.F("regular_price")))
                ),
                name="product_valid_sale_price",
            ),
            models.CheckConstraint(condition=models.Q(stock_quantity__gte=0), name="product_stock_quantity_gte_0"),
            models.UniqueConstraint(Lower("sku"), name="product_sku_ci_unique"),
            models.UniqueConstraint(Lower("slug"), name="product_slug_ci_unique"),
        ]
        indexes = [
            models.Index(fields=["is_published", "category"]),
            models.Index(fields=["is_published", "brand"]),
        ]

    @property
    def selling_price(self):
        return self.sale_price if self.sale_price is not None else self.regular_price

    @property
    def primary_image(self):
        return next(iter(self.images.all()), None)

    def __str__(self):
        return f"{self.name} ({self.sku})"


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/", max_length=255)
    alt_text = models.CharField(max_length=255)
    sort_order = models.PositiveIntegerField()
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [models.UniqueConstraint(fields=["product", "sort_order"], name="product_image_order_unique")]

    def __str__(self):
        return f"{self.product.sku} image {self.sort_order}"


class SpecificationDefinition(models.Model):
    class DataType(models.TextChoices):
        TEXT = "text", "Text"
        INTEGER = "integer", "Integer"
        DECIMAL = "decimal", "Decimal"
        BOOLEAN = "boolean", "Boolean"
        CHOICE = "choice", "Choice"

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="specification_definitions")
    key = models.SlugField(max_length=120)
    label = models.CharField(max_length=120)
    data_type = models.CharField(max_length=10, choices=DataType.choices)
    unit = models.CharField(max_length=40, blank=True)
    is_required = models.BooleanField(default=False)
    is_filterable = models.BooleanField(default=False)
    is_displayed = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "label", "id"]
        constraints = [
            models.UniqueConstraint(fields=["category", "key"], name="spec_definition_category_key_unique"),
        ]

    def __str__(self):
        return f"{self.category}: {self.label}"


class SpecificationChoice(models.Model):
    definition = models.ForeignKey(SpecificationDefinition, on_delete=models.PROTECT, related_name="choices")
    value = models.SlugField(max_length=120)
    label = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "label", "id"]
        constraints = [
            models.UniqueConstraint(fields=["definition", "value"], name="spec_choice_definition_value_unique"),
        ]

    def __str__(self):
        return f"{self.definition}: {self.label}"


class ProductSpecificationValue(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="specification_values")
    definition = models.ForeignKey(
        SpecificationDefinition,
        on_delete=models.PROTECT,
        related_name="product_values",
    )
    text_value = models.TextField(null=True, blank=True)
    integer_value = models.BigIntegerField(null=True, blank=True)
    decimal_value = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    boolean_value = models.BooleanField(null=True, blank=True)
    choice = models.ForeignKey(
        SpecificationChoice,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="product_values",
    )

    class Meta:
        ordering = ["definition__sort_order", "definition__label", "id"]
        constraints = [
            models.UniqueConstraint(fields=["product", "definition"], name="product_spec_value_unique"),
            models.CheckConstraint(
                condition=(
                    (
                        models.Q(text_value__isnull=False)
                        & models.Q(integer_value__isnull=True)
                        & models.Q(decimal_value__isnull=True)
                        & models.Q(boolean_value__isnull=True)
                        & models.Q(choice__isnull=True)
                    )
                    | (
                        models.Q(text_value__isnull=True)
                        & models.Q(integer_value__isnull=False)
                        & models.Q(decimal_value__isnull=True)
                        & models.Q(boolean_value__isnull=True)
                        & models.Q(choice__isnull=True)
                    )
                    | (
                        models.Q(text_value__isnull=True)
                        & models.Q(integer_value__isnull=True)
                        & models.Q(decimal_value__isnull=False)
                        & models.Q(boolean_value__isnull=True)
                        & models.Q(choice__isnull=True)
                    )
                    | (
                        models.Q(text_value__isnull=True)
                        & models.Q(integer_value__isnull=True)
                        & models.Q(decimal_value__isnull=True)
                        & models.Q(boolean_value__isnull=False)
                        & models.Q(choice__isnull=True)
                    )
                    | (
                        models.Q(text_value__isnull=True)
                        & models.Q(integer_value__isnull=True)
                        & models.Q(decimal_value__isnull=True)
                        & models.Q(boolean_value__isnull=True)
                        & models.Q(choice__isnull=False)
                    )
                ),
                name="product_spec_exactly_one_value",
            ),
        ]

    def __str__(self):
        return f"{self.product}: {self.definition.key}"
