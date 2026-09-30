from django.db import transaction
from django.db.models import Sum
from django.http import Http404
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.services import record_audit_event

from .models import InventoryMovement, Product


class StockRestorationError(Exception):
    """An order's saved stock cannot be safely returned to inventory."""


def restore_cancelled_order_stock(*, order, actor):
    """Restore an order's sold units inside the caller's transaction and order lock."""
    items = list(order.items.all())
    quantities = {}
    for item in items:
        if item.product_id is None:
            raise StockRestorationError("An order item no longer has a product to restock.")
        quantities[item.product_id] = quantities.get(item.product_id, 0) + item.quantity
    if not quantities:
        raise StockRestorationError("This order has no items to restock.")
    if InventoryMovement.objects.filter(order=order, reason=InventoryMovement.Reason.ORDER_CANCELLED).exists():
        raise StockRestorationError("This order already has a stock restoration.")
    placed_quantities = {
        row["product_id"]: -row["total"]
        for row in InventoryMovement.objects.filter(
            order=order, reason=InventoryMovement.Reason.ORDER_PLACED,
        ).values("product_id").annotate(total=Sum("quantity_delta"))
    }
    if placed_quantities != quantities:
        raise StockRestorationError("The order's stock deductions do not match its saved items.")

    products = list(Product.objects.select_for_update().filter(pk__in=quantities).order_by("pk"))
    if len(products) != len(quantities):
        raise StockRestorationError("An order product is unavailable for restocking.")
    if any(product.stock_quantity + quantities[product.pk] > 2_147_483_647 for product in products):
        raise StockRestorationError("Restocking would exceed the supported stock quantity.")

    movements = []
    for product in products:
        previous = product.stock_quantity
        product.stock_quantity += quantities[product.pk]
        product.save(update_fields=["stock_quantity", "updated_at"])
        movements.append(InventoryMovement.objects.create(
            product=product, order=order, quantity_delta=quantities[product.pk],
            previous_quantity=previous, new_quantity=product.stock_quantity,
            reason=InventoryMovement.Reason.ORDER_CANCELLED, actor=actor,
        ))
    return movements


@transaction.atomic
def adjust_product_stock(*, product_id, new_quantity, reason, actor):
    if not actor or not actor.is_authenticated or not actor.is_active or not actor.is_staff:
        raise PermissionDenied("Staff access is required.")
    if isinstance(new_quantity, bool) or not isinstance(new_quantity, int) or not 0 <= new_quantity <= 2_147_483_647:
        raise ValidationError({"new_quantity": ["Enter a nonnegative stock quantity."]})
    reason = reason.strip() if isinstance(reason, str) else ""
    if not reason or len(reason) > 500:
        raise ValidationError({"reason": ["Give a reason of at most 500 characters."]})

    try:
        product = Product.objects.select_for_update().get(pk=product_id)
    except Product.DoesNotExist as exc:
        raise Http404("Product not found.") from exc
    previous = product.stock_quantity
    if new_quantity == previous:
        raise ValidationError({"new_quantity": ["New quantity must differ from current stock."]})

    product.stock_quantity = new_quantity
    product.save(update_fields=["stock_quantity", "updated_at"])
    movement = InventoryMovement.objects.create(
        product=product,
        quantity_delta=new_quantity - previous,
        previous_quantity=previous,
        new_quantity=new_quantity,
        reason=InventoryMovement.Reason.MANUAL_ADJUSTMENT,
        note=reason,
        actor=actor,
    )
    record_audit_event(
        actor=actor,
        resource_type="Product",
        resource_id=product.pk,
        action="PRODUCT_STOCK_ADJUSTED",
        before_data={"stock_quantity": previous},
        after_data={"stock_quantity": new_quantity},
        metadata={"reason": reason, "inventory_movement_id": movement.pk},
    )
    return movement
