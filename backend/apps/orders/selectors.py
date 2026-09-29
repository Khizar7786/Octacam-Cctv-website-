from .models import Order


def get_customer_orders(*, user):
    if not user or not user.is_authenticated or not user.is_active or user.is_staff:
        return Order.objects.none()
    return Order.objects.filter(user_id=user.pk).prefetch_related("items").order_by("-placed_at", "-id")
