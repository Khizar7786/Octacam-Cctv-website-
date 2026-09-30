from django.db.models import Count, F, Q
from django.utils import timezone

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
