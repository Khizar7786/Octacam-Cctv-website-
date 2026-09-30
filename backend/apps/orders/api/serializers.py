from urllib.parse import urlsplit

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.audit.models import AuditEvent
from apps.orders.models import Order, OrderItem
from apps.orders.tracking import build_guest_tracking_url


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, dict):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError({key: ["This field is not supported."] for key in sorted(unknown)})
        return super().to_internal_value(data)


class CartItemSerializer(StrictSerializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=1000)


class CartSerializer(StrictSerializer):
    items = CartItemSerializer(many=True, allow_empty=False, max_length=100)
    delivery_city = serializers.CharField(max_length=120)
    delivery_province = serializers.CharField(max_length=120)

    def validate_items(self, value):
        ids = [item["product_id"] for item in value]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("List each product only once.")
        return value


class QuoteRequestSerializer(CartSerializer):
    pass


class PlaceOrderRequestSerializer(CartSerializer):
    quote_token = serializers.CharField(max_length=20000)
    customer_name = serializers.CharField(max_length=160)
    customer_email = serializers.EmailField()
    customer_phone = serializers.CharField(max_length=40)
    delivery_address_line1 = serializers.CharField(max_length=255)
    delivery_address_line2 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    delivery_postal_code = serializers.CharField(max_length=20, required=False, allow_blank=True)
    delivery_country = serializers.ChoiceField(choices=["PK"], required=False, default="PK")


class QuoteItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    name = serializers.CharField()
    sku = serializers.CharField()
    quantity = serializers.IntegerField()
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    regular_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    sale_savings = serializers.DecimalField(max_digits=18, decimal_places=2)
    line_subtotal = serializers.DecimalField(max_digits=18, decimal_places=2)
    tax_amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    stock_quantity = serializers.IntegerField()
    available = serializers.BooleanField()


class QuoteResponseSerializer(serializers.Serializer):
    currency = serializers.CharField()
    items = QuoteItemSerializer(many=True)
    delivery_city = serializers.CharField()
    delivery_province = serializers.CharField()
    subtotal = serializers.DecimalField(max_digits=18, decimal_places=2)
    shipping_fee = serializers.DecimalField(max_digits=18, decimal_places=2)
    shipping_tax_amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    tax_total = serializers.DecimalField(max_digits=18, decimal_places=2)
    grand_total = serializers.DecimalField(max_digits=18, decimal_places=2)
    tax_rate_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    shipping_taxable = serializers.BooleanField()
    payment_method = serializers.CharField()
    quote_token = serializers.CharField(allow_null=True)


class CheckoutConflictSerializer(serializers.Serializer):
    error = serializers.DictField()
    current_quote = QuoteResponseSerializer(allow_null=True)


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ("product_name", "sku", "quantity", "unit_price", "line_subtotal", "tax_amount")


class OrderReceiptSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    guest_tracking_url = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "public_id", "reference", "status", "payment_method", "payment_status", "placed_at",
            "customer_name", "customer_email", "customer_phone",
            "delivery_address_line1", "delivery_address_line2", "delivery_city", "delivery_province",
            "delivery_postal_code", "delivery_country", "items", "subtotal", "shipping_fee",
            "shipping_tax_amount", "tax_total", "grand_total", "guest_tracking_url",
        )

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_guest_tracking_url(self, order):
        if order.user_id is not None:
            return None
        return build_guest_tracking_url(order)


class GuestOrderTrackingSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)

    class Meta:
        model = Order
        fields = (
            "reference", "placed_at", "status", "payment_method", "payment_status", "items",
            "subtotal", "tax_total", "shipping_fee", "grand_total", "courier_name", "tracking_number", "tracking_url",
        )


class CustomerOrderListSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "public_id", "reference", "placed_at", "status", "payment_method", "payment_status",
            "items", "grand_total", "courier_name", "tracking_number", "tracking_url",
        )
        read_only_fields = fields


class CustomerOrderDetailSerializer(CustomerOrderListSerializer):
    class Meta(CustomerOrderListSerializer.Meta):
        fields = (
            *CustomerOrderListSerializer.Meta.fields,
            "customer_name", "customer_email", "customer_phone",
            "delivery_address_line1", "delivery_address_line2", "delivery_city", "delivery_province",
            "delivery_postal_code", "delivery_country", "subtotal", "shipping_fee", "shipping_tax_amount",
            "tax_total", "tax_rate_percent", "shipping_taxable",
        )
        read_only_fields = fields


class StaffOrderFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.Status.choices, required=False)
    payment_status = serializers.ChoiceField(choices=Order.PaymentStatus.choices, required=False)
    q = serializers.CharField(max_length=80, required=False, trim_whitespace=True)


class StaffOrderListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = (
            "public_id", "reference", "customer_name", "customer_email", "placed_at",
            "status", "payment_method", "payment_status", "grand_total",
            "courier_name", "tracking_number", "tracking_url", "version", "updated_at",
        )
        read_only_fields = fields


class StaffOrderDetailSerializer(StaffOrderListSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta(StaffOrderListSerializer.Meta):
        fields = (
            *StaffOrderListSerializer.Meta.fields,
            "customer_phone", "delivery_address_line1", "delivery_address_line2",
            "delivery_city", "delivery_province", "delivery_postal_code", "delivery_country",
            "items", "subtotal", "shipping_fee", "shipping_tax_amount", "tax_total",
            "tax_rate_percent", "shipping_taxable",
        )
        read_only_fields = fields


class StaffOrderTransitionSerializer(StrictSerializer):
    status = serializers.ChoiceField(choices=Order.Status.choices)
    expected_version = serializers.IntegerField(min_value=0)


class StaffOrderCourierSerializer(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=0)
    courier_name = serializers.CharField(max_length=120, required=False, allow_blank=True, trim_whitespace=True)
    tracking_number = serializers.CharField(max_length=120, required=False, allow_blank=True, trim_whitespace=True)
    tracking_url = serializers.URLField(max_length=200, required=False, allow_blank=True)

    def validate_tracking_url(self, value):
        if value and urlsplit(value).scheme.lower() not in {"http", "https"}:
            raise serializers.ValidationError("Use an HTTP or HTTPS tracking link.")
        return value

    def validate(self, attrs):
        if not any(field in attrs for field in ("courier_name", "tracking_number", "tracking_url")):
            raise serializers.ValidationError({"courier": ["Provide at least one courier field."]})
        return attrs


class StaffOrderCodCollectedSerializer(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=0)


class StaffOrderAuditSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(source="actor.email", read_only=True, allow_null=True)

    class Meta:
        model = AuditEvent
        fields = ("id", "action", "actor_email", "before_data", "after_data", "metadata", "created_at")
        read_only_fields = fields
