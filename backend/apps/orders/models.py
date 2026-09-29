import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Order(models.Model):
    class Status(models.TextChoices):
        PLACED = "placed", "Placed"
        CONFIRMED = "confirmed", "Confirmed"
        PACKED = "packed", "Packed"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    class PaymentMethod(models.TextChoices):
        COD = "COD", "Cash on delivery"

    class PaymentStatus(models.TextChoices):
        UNCOLLECTED = "uncollected", "Uncollected"
        COLLECTED = "collected", "Collected"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    reference = models.CharField(max_length=24, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="orders")
    customer_name = models.CharField(max_length=160)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=40)
    delivery_address_line1 = models.CharField(max_length=255)
    delivery_address_line2 = models.CharField(max_length=255, blank=True)
    delivery_city = models.CharField(max_length=120)
    delivery_province = models.CharField(max_length=120)
    delivery_postal_code = models.CharField(max_length=20, blank=True)
    delivery_country = models.CharField(max_length=2, default="PK")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PLACED)
    payment_method = models.CharField(max_length=3, choices=PaymentMethod.choices, default=PaymentMethod.COD)
    payment_status = models.CharField(max_length=12, choices=PaymentStatus.choices, default=PaymentStatus.UNCOLLECTED)
    subtotal = models.DecimalField(max_digits=18, decimal_places=2)
    tax_total = models.DecimalField(max_digits=18, decimal_places=2)
    shipping_fee = models.DecimalField(max_digits=18, decimal_places=2)
    shipping_tax_amount = models.DecimalField(max_digits=18, decimal_places=2)
    grand_total = models.DecimalField(max_digits=18, decimal_places=2)
    tax_rate_percent = models.DecimalField(max_digits=5, decimal_places=2)
    shipping_taxable = models.BooleanField()
    courier_name = models.CharField(max_length=120, blank=True)
    tracking_number = models.CharField(max_length=120, blank=True)
    tracking_url = models.URLField(blank=True)
    idempotency_key = models.UUIDField(unique=True)
    request_fingerprint = models.CharField(max_length=64)
    guest_link_nonce = models.UUIDField(default=uuid.uuid4)
    placed_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-placed_at", "-id"]
        indexes = [models.Index(fields=["status", "-placed_at"]), models.Index(fields=["payment_status", "-placed_at"])]
        constraints = [
            models.CheckConstraint(condition=models.Q(subtotal__gte=0), name="order_subtotal_nonnegative"),
            models.CheckConstraint(condition=models.Q(tax_total__gte=0), name="order_tax_nonnegative"),
            models.CheckConstraint(condition=models.Q(shipping_fee__gte=0), name="order_shipping_nonnegative"),
            models.CheckConstraint(condition=models.Q(grand_total__gte=0), name="order_grand_nonnegative"),
        ]

    def __str__(self):
        return self.reference


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="items")
    product = models.ForeignKey("catalog.Product", null=True, blank=True, on_delete=models.SET_NULL)
    product_name = models.CharField(max_length=255)
    sku = models.CharField(max_length=120)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_subtotal = models.DecimalField(max_digits=18, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gte=1), name="order_item_quantity_positive"),
            models.CheckConstraint(condition=models.Q(unit_price__gte=0), name="order_item_price_nonnegative"),
            models.CheckConstraint(condition=models.Q(line_subtotal__gte=0), name="order_item_subtotal_nonnegative"),
            models.CheckConstraint(condition=models.Q(tax_amount__gte=0), name="order_item_tax_nonnegative"),
        ]


ORDER_STATUS_CHOICES = Order.Status.choices
