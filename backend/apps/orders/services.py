import hashlib
import json
import uuid
from decimal import Decimal

from django.core import signing
from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from apps.audit.services import record_audit_event
from apps.catalog.models import InventoryMovement, Product
from apps.communications.models import EmailOutbox
from apps.communications.services import enqueue_email

from .models import Order, OrderItem
from .pricing import PricingPolicy


QUOTE_SALT = "octacam.checkout.quote.v1"
QUOTE_MAX_AGE_SECONDS = 15 * 60
MAX_AMOUNT = Decimal("9999999999999999.99")


class CheckoutConflict(Exception):
    def __init__(self, code, message, current_quote=None):
        self.code = code
        self.message = message
        self.current_quote = current_quote
        super().__init__(message)


def canonical_items(items):
    return [{"product_id": row["product_id"], "quantity": row["quantity"]} for row in sorted(items, key=lambda row: row["product_id"])]


def location(data):
    return {"city": data["delivery_city"].strip().casefold(), "province": data["delivery_province"].strip().casefold()}


def quote_snapshot(*, items, delivery_city, delivery_province, products=None):
    policy = PricingPolicy.configured()
    rows = canonical_items(items)
    if products is None:
        products = Product.objects.select_related("brand", "category").filter(
            pk__in=[row["product_id"] for row in rows]
        ).order_by("pk")
    products_by_id = {product.pk: product for product in products}
    if len(products_by_id) != len(rows) or any(
        not product.is_published or not product.brand.is_active or not product.category.is_active
        for product in products_by_id.values()
    ):
        raise ValidationError({"items": ["A selected product is unavailable."]})

    result_items = []
    subtotal = Decimal("0.00")
    item_tax_total = Decimal("0.00")
    for row in rows:
        product = products_by_id[row["product_id"]]
        quantity = row["quantity"]
        line_subtotal = product.selling_price * quantity
        line_tax = policy.tax_on(line_subtotal)
        subtotal += line_subtotal
        item_tax_total += line_tax
        result_items.append({
            "product_id": product.pk, "name": product.name, "sku": product.sku,
            "quantity": quantity, "unit_price": str(product.selling_price),
            "regular_price": str(product.regular_price),
            "sale_savings": str((product.regular_price - product.selling_price) * quantity),
            "line_subtotal": str(line_subtotal), "tax_amount": str(line_tax),
            "stock_quantity": product.stock_quantity,
            "available": product.stock_quantity >= quantity,
        })
    shipping_tax = policy.tax_on(policy.shipping_fee) if policy.shipping_taxable else Decimal("0.00")
    tax_total = item_tax_total + shipping_tax
    grand_total = subtotal + tax_total + policy.shipping_fee
    if grand_total > MAX_AMOUNT:
        raise ValidationError({"items": ["The order total is too large."]})
    snapshot = {
        "currency": "PKR", "items": result_items,
        "delivery_city": delivery_city, "delivery_province": delivery_province,
        "subtotal": str(subtotal), "shipping_fee": str(policy.shipping_fee),
        "shipping_tax_amount": str(shipping_tax), "tax_total": str(tax_total),
        "grand_total": str(grand_total), "tax_rate_percent": str(policy.tax_rate_percent),
        "shipping_taxable": policy.shipping_taxable, "payment_method": Order.PaymentMethod.COD,
    }
    return snapshot


def signed_quote(snapshot):
    return {**snapshot, "quote_token": signing.dumps(snapshot, salt=QUOTE_SALT, compress=True) if all(
        row["available"] for row in snapshot["items"]
    ) else None}


def create_quote(data):
    snapshot = quote_snapshot(**data)
    if not all(row["available"] for row in snapshot["items"]):
        raise CheckoutConflict("OUT_OF_STOCK", "A selected quantity is no longer available.", signed_quote(snapshot))
    return signed_quote(snapshot)


def _request_fingerprint(data, user_id):
    canonical = {
        "user_id": user_id,
        "items": canonical_items(data["items"]),
        "quote_token": data["quote_token"],
        "customer_name": data["customer_name"],
        "customer_email": data["customer_email"].lower(),
        "customer_phone": data["customer_phone"],
        "delivery_address_line1": data["delivery_address_line1"],
        "delivery_address_line2": data.get("delivery_address_line2", ""),
        "delivery_city": data["delivery_city"],
        "delivery_province": data["delivery_province"],
        "delivery_postal_code": data.get("delivery_postal_code", ""),
    }
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _existing_order(key, fingerprint):
    order = Order.objects.filter(idempotency_key=key).prefetch_related("items").first()
    if order and order.request_fingerprint != fingerprint:
        raise CheckoutConflict("IDEMPOTENCY_CONFLICT", "This idempotency key was used for a different request.")
    return order


def _read_quote_token(token):
    try:
        return signing.loads(token, salt=QUOTE_SALT, max_age=QUOTE_MAX_AGE_SECONDS)
    except signing.BadSignature as exc:
        raise ValidationError({"quote_token": ["The quote is invalid or expired. Request a new quote."]}) from exc


@transaction.atomic
def place_order(*, data, idempotency_key, user):
    user = user if user and user.is_authenticated else None
    fingerprint = _request_fingerprint(data, user.pk if user else None)
    existing = _existing_order(idempotency_key, fingerprint)
    if existing:
        return existing, False

    reviewed = _read_quote_token(data["quote_token"])
    if (
        canonical_items(data["items"]) != [
            {"product_id": row["product_id"], "quantity": row["quantity"]} for row in reviewed["items"]
        ]
        or location(data) != location(reviewed)
    ):
        raise ValidationError({"quote_token": ["The quote does not match the items or delivery location."]})

    rows = canonical_items(data["items"])
    # Parent locks keep brand/category eligibility stable until this placement commits.
    locked = list(Product.objects.select_related("brand", "category").select_for_update(
        of=("self", "brand", "category")
    ).filter(
        pk__in=[row["product_id"] for row in rows]
    ).order_by("pk"))
    # Recheck after acquiring the product locks: a concurrent request with this key may have committed.
    existing = _existing_order(idempotency_key, fingerprint)
    if existing:
        return existing, False
    if len(locked) != len(rows) or any(
        not product.is_published or not product.brand.is_active or not product.category.is_active for product in locked
    ):
        raise CheckoutConflict("CHECKOUT_CHANGED", "A selected product is no longer available. Review your cart.")
    current = quote_snapshot(items=rows, delivery_city=data["delivery_city"],
                             delivery_province=data["delivery_province"], products=locked)
    if current != reviewed:
        raise CheckoutConflict("CHECKOUT_CHANGED", "The price or availability changed. Review the updated quote.", signed_quote(current))

    public_id = uuid.uuid4()
    try:
        # The unique key also protects concurrent same-key requests with disjoint product sets.
        with transaction.atomic():
            order = Order.objects.create(
                public_id=public_id, reference=f"OC-{public_id.hex[:16].upper()}",
                user=user, customer_name=data["customer_name"], customer_email=data["customer_email"].lower(),
                customer_phone=data["customer_phone"],
                delivery_address_line1=data["delivery_address_line1"],
                delivery_address_line2=data.get("delivery_address_line2", ""),
                delivery_city=data["delivery_city"], delivery_province=data["delivery_province"],
                delivery_postal_code=data.get("delivery_postal_code", ""),
                subtotal=Decimal(current["subtotal"]), tax_total=Decimal(current["tax_total"]),
                shipping_fee=Decimal(current["shipping_fee"]),
                shipping_tax_amount=Decimal(current["shipping_tax_amount"]),
                grand_total=Decimal(current["grand_total"]),
                tax_rate_percent=Decimal(current["tax_rate_percent"]),
                shipping_taxable=current["shipping_taxable"],
                idempotency_key=idempotency_key, request_fingerprint=fingerprint,
            )
    except IntegrityError:
        existing = _existing_order(idempotency_key, fingerprint)
        if existing:
            return existing, False
        raise

    products_by_id = {product.pk: product for product in locked}
    for item in current["items"]:
        product = products_by_id[item["product_id"]]
        previous = product.stock_quantity
        new_quantity = previous - item["quantity"]
        OrderItem.objects.create(
            order=order, product=product, product_name=item["name"], sku=item["sku"],
            quantity=item["quantity"], unit_price=Decimal(item["unit_price"]),
            line_subtotal=Decimal(item["line_subtotal"]), tax_amount=Decimal(item["tax_amount"]),
        )
        product.stock_quantity = new_quantity
        product.save(update_fields=["stock_quantity", "updated_at"])
        InventoryMovement.objects.create(
            product=product, order=order, quantity_delta=-item["quantity"],
            previous_quantity=previous, new_quantity=new_quantity,
            reason=InventoryMovement.Reason.ORDER_PLACED, actor=user,
        )
    record_audit_event(
        actor=user, resource_type="Order", resource_id=order.pk, action="ORDER_PLACED",
        before_data={}, after_data={"status": order.status, "grand_total": str(order.grand_total)},
        metadata={"product_ids": [row["product_id"] for row in rows]},
    )
    enqueue_email(
        event_type=EmailOutbox.EventType.ORDER_PLACED, recipient=order.customer_email,
        template_name="order_placed", context={"order_id": order.pk},
        dedupe_key=f"order:{order.public_id}:placed", order=order,
    )
    return order, True
