from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.audit.models import AuditEvent
from apps.communications.models import EmailOutbox
from apps.orders.models import Order
from apps.orders.selectors import get_staff_orders
from apps.surveys.selectors import get_upcoming_survey_bookings


OPEN_ORDER_STATUSES = (
    Order.Status.PLACED, Order.Status.CONFIRMED,
    Order.Status.PACKED, Order.Status.SHIPPED,
)


def get_staff_activity(*, user):
    if not user or not user.is_authenticated or not user.is_active or not user.is_staff:
        return AuditEvent.objects.none()
    return AuditEvent.objects.select_related("actor").order_by("-created_at", "-id")


def get_staff_overview(*, user, preview_size):
    if not user or not user.is_authenticated or not user.is_active or not user.is_staff:
        raise PermissionDenied("Staff access is required.")
    now = timezone.now()
    orders = get_staff_orders(user=user)
    upcoming = get_upcoming_survey_bookings(user=user, now=now)
    activity = get_staff_activity(user=user)
    failed = EmailOutbox.objects.filter(status=EmailOutbox.Status.FAILED).order_by("-created_at", "-id")
    return {
        "placed_orders_count": orders.filter(status=Order.Status.PLACED).count(),
        "open_orders_count": orders.filter(status__in=OPEN_ORDER_STATUSES).count(),
        "upcoming_surveys_count": upcoming.count(),
        "failed_emails_count": failed.count(),
        "recent_orders": list(orders[:preview_size]),
        "upcoming_surveys": list(upcoming[:preview_size]),
        "recent_activity": list(activity[:preview_size]),
        "failed_emails": list(failed[:preview_size]),
    }
