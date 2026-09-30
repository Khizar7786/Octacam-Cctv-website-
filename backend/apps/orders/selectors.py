from apps.audit.models import AuditEvent

from .models import Order


def get_customer_orders(*, user):
    if not user or not user.is_authenticated or not user.is_active or user.is_staff:
        return Order.objects.none()
    return Order.objects.filter(user_id=user.pk).prefetch_related("items").order_by("-placed_at", "-id")


def get_staff_orders(*, user, status=None, payment_status=None, q=None):
    if not user or not user.is_authenticated or not user.is_active or not user.is_staff:
        return Order.objects.none()
    orders = Order.objects.all()
    if status:
        orders = orders.filter(status=status)
    if payment_status:
        orders = orders.filter(payment_status=payment_status)
    if q:
        orders = orders.filter(reference__icontains=q)
    return orders.order_by("-placed_at", "-id")


def get_order_audit_history(*, order):
    return AuditEvent.objects.filter(resource_type="Order", resource_id=str(order.pk)).select_related("actor")
