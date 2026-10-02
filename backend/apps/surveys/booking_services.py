import hashlib
import json
import uuid

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.services import record_audit_event
from apps.communications.models import EmailOutbox
from apps.communications.services import enqueue_email

from .models import SurveyBooking, SurveySlot
from .services import SurveyConfigurationError


INSTALLATION_NOTICE = "This booking is for a free site survey. Installation is quoted and scheduled afterward."
BOOKING_FIELDS = (
    "customer_name", "customer_email", "customer_phone", "site_address_line1",
    "site_address_line2", "site_area", "site_city", "needs_description",
)


class SurveyBookingConflict(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


def _configured_areas():
    try:
        areas = json.loads(settings.SURVEY_LAHORE_SERVICE_AREAS)
    except (TypeError, ValueError) as exc:
        raise SurveyConfigurationError("Approved Lahore service areas are not configured.") from exc
    if not isinstance(areas, list) or not areas or any(
        not isinstance(area, str) or not area.strip() or len(area.strip()) > 120 for area in areas
    ):
        raise SurveyConfigurationError("Approved Lahore service areas are not configured.")
    return {area.strip().casefold() for area in areas}


def _validate_service_area(data):
    areas = _configured_areas()
    if data["site_city"].strip().casefold() != "lahore":
        raise ValidationError({"site_city": ["Site surveys are available only in the approved Lahore service area."]})
    if data["site_area"].strip().casefold() not in areas:
        raise ValidationError({"site_area": ["This area is outside the approved Lahore survey coverage. Contact support for help."]})


def _request_fingerprint(data, user_id, related_order_id=None):
    canonical = {
        "user_id": user_id, "slot_public_id": str(data["slot_public_id"]),
        **{field: data.get(field, "").strip() for field in BOOKING_FIELDS},
    }
    canonical["customer_email"] = canonical["customer_email"].lower()
    if related_order_id is not None:
        canonical["related_order_id"] = related_order_id
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _existing_booking(key, fingerprint):
    booking = SurveyBooking.objects.select_related("slot").filter(idempotency_key=key).first()
    if booking and booking.request_fingerprint != fingerprint:
        raise SurveyBookingConflict("IDEMPOTENCY_CONFLICT", "This idempotency key was used for a different request.")
    return booking


@transaction.atomic
def book_survey(*, data, idempotency_key, user, related_order=None):
    """Create a booking, audit, and email; checkout supplies its order inside the outer transaction."""
    user = user if user and user.is_authenticated else None
    fingerprint = _request_fingerprint(data, user.pk if user else None, related_order.pk if related_order else None)
    existing = _existing_booking(idempotency_key, fingerprint)
    if existing:
        return existing, False

    slot = SurveySlot.objects.select_for_update().filter(public_id=data["slot_public_id"]).first()
    # A retry can have waited for the first request to commit while acquiring this lock.
    existing = _existing_booking(idempotency_key, fingerprint)
    if existing:
        return existing, False
    _validate_service_area(data)
    if slot is None or not slot.is_open or slot.starts_at <= timezone.now() or (
        slot.bookings.exclude(status=SurveyBooking.Status.CANCELLED).count() >= slot.capacity
    ):
        raise SurveyBookingConflict("SURVEY_SLOT_UNAVAILABLE", "That survey slot is no longer available. Choose another slot.")

    public_id = uuid.uuid4()
    try:
        # A unique key also serializes concurrent submissions selecting different slots.
        with transaction.atomic():
            booking = SurveyBooking.objects.create(
                public_id=public_id, reference=f"OCS-{public_id.hex[:16].upper()}",
                slot=slot, scheduled_starts_at=slot.starts_at, scheduled_ends_at=slot.ends_at,
                user=user, related_order=related_order,
                **{field: data.get(field, "").strip() for field in BOOKING_FIELDS if field != "customer_email"},
                customer_email=data["customer_email"].strip().lower(),
                idempotency_key=idempotency_key, request_fingerprint=fingerprint,
            )
    except IntegrityError:
        existing = _existing_booking(idempotency_key, fingerprint)
        if existing:
            return existing, False
        raise
    record_audit_event(
        actor=user, resource_type="SurveyBooking", resource_id=booking.pk,
        action="SURVEY_BOOKING_CONFIRMED", before_data={}, after_data={"status": booking.status},
        metadata={"slot_public_id": str(slot.public_id),
                  **({"related_order_public_id": str(related_order.public_id)} if related_order else {})},
    )
    enqueue_email(
        event_type=EmailOutbox.EventType.SURVEY_CONFIRMED,
        recipient=booking.customer_email, template_name="survey_confirmed",
        context={"survey_booking_id": booking.pk, "starts_at": slot.starts_at.isoformat(), "ends_at": slot.ends_at.isoformat()},
        dedupe_key=f"survey:{booking.public_id}:confirmed", survey_booking=booking,
    )
    return booking, True
