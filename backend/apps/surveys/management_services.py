from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.services import record_audit_event
from apps.communications.models import EmailOutbox
from apps.communications.services import enqueue_email

from .booking_services import SurveyBookingConflict
from .models import SurveyBooking, SurveySlot
from .services import _require_staff


def _locked_booking(*, public_id, expected_version, actor):
    _require_staff(actor)
    try:
        booking = SurveyBooking.objects.select_for_update().get(public_id=public_id)
    except SurveyBooking.DoesNotExist as exc:
        raise Http404("Survey booking not found.") from exc
    if isinstance(expected_version, bool) or not isinstance(expected_version, int) or expected_version < 0:
        raise ValidationError({"expected_version": ["Enter the version shown on the booking."]})
    if booking.version != expected_version:
        raise SurveyBookingConflict("BOOKING_CHANGED", "This booking changed. Reload it before saving.")
    return booking


def _snapshot(booking):
    return {
        "status": booking.status, "slot_public_id": str(booking.slot.public_id),
        "starts_at": booking.scheduled_starts_at.isoformat(),
        "ends_at": booking.scheduled_ends_at.isoformat(),
    }


def _record_change(*, booking, actor, action, before, event_type, template_name):
    after = _snapshot(booking)
    audit = record_audit_event(
        actor=actor, resource_type="SurveyBooking", resource_id=booking.pk, action=action,
        before_data=before, after_data=after, metadata={"version": booking.version},
    )
    enqueue_email(
        event_type=event_type, recipient=booking.customer_email, template_name=template_name,
        context={"survey_booking_id": booking.pk, "change": action, "before": before, "after": after},
        dedupe_key=f"survey:{booking.public_id}:change:{audit.pk}", survey_booking=booking,
    )


@transaction.atomic
def reschedule_survey(*, public_id, slot_public_id, expected_version, actor):
    booking = _locked_booking(public_id=public_id, expected_version=expected_version, actor=actor)
    if booking.status != SurveyBooking.Status.CONFIRMED:
        raise SurveyBookingConflict("BOOKING_CLOSED", "Only a confirmed survey can be rescheduled.")
    # All moves lock their slot pair in the same order, including moves in opposite directions.
    slots = list(SurveySlot.objects.select_for_update().filter(
        Q(pk=booking.slot_id) | Q(public_id=slot_public_id),
    ).order_by("pk"))
    old_slot = next(slot for slot in slots if slot.pk == booking.slot_id)
    destination = next((slot for slot in slots if slot.public_id == slot_public_id), None)
    booking.slot = old_slot
    if destination is not None and destination.pk == old_slot.pk:
        return booking
    if destination is None or not destination.is_open or destination.starts_at <= timezone.now() or (
        destination.bookings.exclude(status=SurveyBooking.Status.CANCELLED).count() >= destination.capacity
    ):
        raise SurveyBookingConflict("SURVEY_SLOT_UNAVAILABLE", "That survey slot is no longer available. Choose another slot.")
    before = _snapshot(booking)
    booking.slot = destination
    booking.scheduled_starts_at = destination.starts_at
    booking.scheduled_ends_at = destination.ends_at
    booking.version += 1
    booking.save(update_fields=["slot", "scheduled_starts_at", "scheduled_ends_at", "version", "updated_at"])
    _record_change(
        booking=booking, actor=actor, action="SURVEY_BOOKING_RESCHEDULED", before=before,
        event_type=EmailOutbox.EventType.SURVEY_CHANGED, template_name="survey_changed",
    )
    return booking


@transaction.atomic
def transition_survey(*, public_id, status, expected_version, actor):
    booking = _locked_booking(public_id=public_id, expected_version=expected_version, actor=actor)
    if status not in (SurveyBooking.Status.COMPLETED, SurveyBooking.Status.CANCELLED):
        raise ValidationError({"status": ["Choose completed or cancelled."]})
    if booking.status == status:
        return booking
    if booking.status != SurveyBooking.Status.CONFIRMED:
        raise SurveyBookingConflict("BOOKING_CLOSED", "Completed and cancelled surveys cannot change state.")
    # Cancellation and completion use the same capacity lock as booking and rescheduling.
    booking.slot = SurveySlot.objects.select_for_update().get(pk=booking.slot_id)
    before = _snapshot(booking)
    booking.status = status
    booking.version += 1
    booking.save(update_fields=["status", "version", "updated_at"])
    cancelled = status == SurveyBooking.Status.CANCELLED
    _record_change(
        booking=booking, actor=actor,
        action="SURVEY_BOOKING_CANCELLED" if cancelled else "SURVEY_BOOKING_COMPLETED", before=before,
        event_type=EmailOutbox.EventType.SURVEY_CANCELLED if cancelled else EmailOutbox.EventType.SURVEY_CHANGED,
        template_name="survey_cancelled" if cancelled else "survey_changed",
    )
    return booking


@transaction.atomic
def update_survey_notes(*, public_id, internal_notes, expected_version, actor):
    booking = _locked_booking(public_id=public_id, expected_version=expected_version, actor=actor)
    if not isinstance(internal_notes, str) or len(internal_notes) > 10000:
        raise ValidationError({"internal_notes": ["Enter notes of at most 10000 characters."]})
    if booking.internal_notes == internal_notes:
        return booking
    before = booking.internal_notes
    booking.internal_notes = internal_notes
    booking.version += 1
    booking.save(update_fields=["internal_notes", "version", "updated_at"])
    record_audit_event(
        actor=actor, resource_type="SurveyBooking", resource_id=booking.pk, action="SURVEY_BOOKING_NOTES_UPDATED",
        before_data={"internal_notes": before}, after_data={"internal_notes": internal_notes},
        metadata={"version": booking.version},
    )
    return booking
