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

    @property
    def selling_price(self):
        return self.sale_price if self.sale_price is not None else self.regular_price

    def __str__(self):
        return f"{self.name} ({self.sku})"
