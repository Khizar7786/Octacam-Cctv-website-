from django.db.models import Count, F, Q
from django.utils import timezone

from apps.audit.models import AuditEvent

from .models import SurveyBooking, SurveySlot


def slots_with_occupancy():
    """Count persisted bookings; a cancelled booking releases its place."""
    return SurveySlot.objects.annotate(
        booked_count=Count("bookings", filter=~Q(bookings__status=SurveyBooking.Status.CANCELLED)),
    )


def public_available_slots():
    return (
        slots_with_occupancy()
        .filter(is_open=True, starts_at__gt=timezone.now(), booked_count__lt=F("capacity"))
        .order_by("starts_at", "id")
    )


def staff_slots():
    return slots_with_occupancy().order_by("starts_at", "id")


def staff_bookings(*, user, status=None, q=None, upcoming=False, now=None):
    if not user or not user.is_authenticated or not user.is_active or not user.is_staff:
        return SurveyBooking.objects.none()
    bookings = SurveyBooking.objects.select_related("slot", "related_order")
    if status:
        bookings = bookings.filter(status=status)
    if q:
        bookings = bookings.filter(reference__icontains=q)
    if upcoming:
        return bookings.filter(
            status=SurveyBooking.Status.CONFIRMED,
            scheduled_starts_at__gt=now if now is not None else timezone.now(),
        ).order_by("scheduled_starts_at", "id")
    return bookings.order_by("-created_at", "-id")


def get_upcoming_survey_bookings(*, user, now=None):
    return staff_bookings(user=user, upcoming=True, now=now)


def booking_audit_history(*, booking):
    return AuditEvent.objects.filter(
        resource_type="SurveyBooking", resource_id=str(booking.pk),
    ).select_related("actor")
