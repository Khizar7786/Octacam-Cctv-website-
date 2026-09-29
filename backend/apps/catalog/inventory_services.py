from django.db import transaction
from django.http import Http404
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.services import record_audit_event

from .models import InventoryMovement, Product


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
