from django.db import transaction
from django.http import Http404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.services import record_audit_event
from apps.catalog.inventory_services import StockRestorationError, restore_cancelled_order_stock
from apps.communications.models import EmailOutbox
from apps.communications.services import enqueue_email

from .models import Order


NEXT_STATUS = {
    Order.Status.PLACED: Order.Status.CONFIRMED,
    Order.Status.CONFIRMED: Order.Status.PACKED,
    Order.Status.PACKED: Order.Status.SHIPPED,
    Order.Status.SHIPPED: Order.Status.DELIVERED,
}
COURIER_FIELDS = ("courier_name", "tracking_number", "tracking_url")
CANCELLABLE_STATUSES = {Order.Status.PLACED, Order.Status.CONFIRMED}


class OrderCommandConflict(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


def _locked_order(*, public_id, actor):
    if not actor or not actor.is_authenticated or not actor.is_active or not actor.is_staff:
        raise PermissionDenied("Staff access is required.")
    try:
        return Order.objects.select_for_update().get(public_id=public_id)
    except Order.DoesNotExist as exc:
        raise Http404("Order not found.") from exc


def _check_version(order, expected_version):
    if isinstance(expected_version, bool) or not isinstance(expected_version, int) or expected_version < 0:
        raise ValidationError({"expected_version": ["Enter the version shown on the order."]})
    if order.version != expected_version:
        raise OrderCommandConflict("ORDER_CHANGED", "This order changed. Reload it before saving.")


@transaction.atomic
def transition_order(*, public_id, status, expected_version, actor):
    order = _locked_order(public_id=public_id, actor=actor)
    if NEXT_STATUS.get(order.status) != status:
        raise OrderCommandConflict("INVALID_STATUS_TRANSITION", "This fulfillment transition is not allowed.")
    _check_version(order, expected_version)

    previous_status = order.status
    order.status = status
    order.version += 1
    order.save(update_fields=["status", "version", "updated_at"])
    audit = record_audit_event(
        actor=actor, resource_type="Order", resource_id=order.pk, action="ORDER_STATUS_CHANGED",
        before_data={"status": previous_status}, after_data={"status": status},
        metadata={"version": order.version},
    )
    enqueue_email(
        event_type=EmailOutbox.EventType.ORDER_STATUS_CHANGED,
        recipient=order.customer_email, template_name="order_status_changed",
        context={
            "order_id": order.pk, "from_status": previous_status, "to_status": status,
            **{field: getattr(order, field) for field in COURIER_FIELDS},
        },
        dedupe_key=f"order:{order.public_id}:status-change:{audit.pk}", order=order,
    )
    return order


@transaction.atomic
def update_order_courier(*, public_id, data, expected_version, actor):
    order = _locked_order(public_id=public_id, actor=actor)
    if order.status == Order.Status.CANCELLED:
        raise OrderCommandConflict("ORDER_CLOSED", "Courier details cannot be changed on a cancelled order.")
    changes = {field: data[field] for field in COURIER_FIELDS if field in data and data[field] != getattr(order, field)}
    if not changes:
        return order
    _check_version(order, expected_version)

    before = {field: getattr(order, field) for field in COURIER_FIELDS}
    for field, value in changes.items():
        setattr(order, field, value)
    order.version += 1
    order.save(update_fields=[*changes, "version", "updated_at"])
    record_audit_event(
        actor=actor, resource_type="Order", resource_id=order.pk, action="COURIER_UPDATED",
        before_data=before,
        after_data={field: getattr(order, field) for field in COURIER_FIELDS},
        metadata={"version": order.version},
    )
    return order


@transaction.atomic
def mark_order_cod_collected(*, public_id, expected_version, actor):
    order = _locked_order(public_id=public_id, actor=actor)
    if order.status == Order.Status.CANCELLED:
        raise OrderCommandConflict("ORDER_CLOSED", "COD cannot be collected on a cancelled order.")
    if order.payment_status == Order.PaymentStatus.COLLECTED:
        return order
    _check_version(order, expected_version)

    previous_status = order.payment_status
    order.payment_status = Order.PaymentStatus.COLLECTED
    order.version += 1
    order.save(update_fields=["payment_status", "version", "updated_at"])
    record_audit_event(
        actor=actor, resource_type="Order", resource_id=order.pk, action="COD_MARKED_COLLECTED",
        before_data={"payment_status": previous_status},
        after_data={"payment_status": order.payment_status},
        metadata={"version": order.version},
    )
    return order


@transaction.atomic
def cancel_order(*, public_id, expected_version, reason, actor):
    order = _locked_order(public_id=public_id, actor=actor)
    if order.status == Order.Status.CANCELLED:
        return order
    _check_version(order, expected_version)
    reason = reason.strip() if isinstance(reason, str) else ""
    if not reason or len(reason) > 500:
        raise ValidationError({"reason": ["Give a reason of at most 500 characters."]})
    if order.status not in CANCELLABLE_STATUSES or order.payment_status != Order.PaymentStatus.UNCOLLECTED:
        raise OrderCommandConflict(
            "CANCELLATION_NOT_ALLOWED",
            "Only placed or confirmed orders with uncollected COD can be cancelled by staff.",
        )

    try:
        movements = restore_cancelled_order_stock(order=order, actor=actor)
    except StockRestorationError as exc:
        raise OrderCommandConflict("RESTOCK_UNAVAILABLE", str(exc)) from exc

    previous_status = order.status
    order.status = Order.Status.CANCELLED
    order.cancelled_at = timezone.now()
    order.version += 1
    order.save(update_fields=["status", "cancelled_at", "version", "updated_at"])
    record_audit_event(
        actor=actor, resource_type="Order", resource_id=order.pk, action="ORDER_CANCELLED",
        before_data={"status": previous_status}, after_data={"status": order.status},
        metadata={"version": order.version, "reason": reason, "restocked": True,
                  "inventory_movement_ids": [movement.pk for movement in movements]},
    )
    enqueue_email(
        event_type=EmailOutbox.EventType.ORDER_CANCELLED,
        recipient=order.customer_email, template_name="order_cancelled",
        context={"order_id": order.pk, "from_status": previous_status},
        dedupe_key=f"order:{order.public_id}:cancelled", order=order,
    )
    return order
