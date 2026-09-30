from datetime import timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import Http404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.services import record_audit_event

from .models import SurveyBooking, SurveySlot


KARACHI = ZoneInfo("Asia/Karachi")


class SurveySlotConflict(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


class SurveyConfigurationError(Exception):
    pass


def configured_slot_duration():
    raw = getattr(settings, "SURVEY_SLOT_DURATION_MINUTES", None)
    try:
        if isinstance(raw, bool):
            raise ValueError
        minutes = int(raw)
        if minutes < 1:
            raise ValueError
        return timedelta(minutes=minutes)
    except (TypeError, ValueError, OverflowError) as exc:
        raise SurveyConfigurationError("An approved survey slot duration is not configured.") from exc


def _require_staff(actor):
    if not actor or not actor.is_authenticated or not actor.is_active or not actor.is_staff:
        raise PermissionDenied("Staff access is required.")


def _validate_start(starts_at):
    if timezone.is_naive(starts_at):
        raise ValidationError({"starts_at": ["Include a timezone offset."]})
    if starts_at <= timezone.now():
        raise ValidationError({"starts_at": ["Choose a future survey time."]})


def _validate_capacity(capacity):
    if isinstance(capacity, bool) or not isinstance(capacity, int) or not 1 <= capacity <= 2_147_483_647:
        raise ValidationError({"capacity": ["Enter a positive capacity."]})


def _snapshot(slot):
    return {
        "starts_at": timezone.localtime(slot.starts_at, KARACHI).isoformat(),
        "ends_at": timezone.localtime(slot.ends_at, KARACHI).isoformat(),
        "capacity": slot.capacity,
        "is_open": slot.is_open,
    }


@transaction.atomic
def create_slot(*, starts_at, capacity, is_open=True, actor):
    _require_staff(actor)
    _validate_start(starts_at)
    _validate_capacity(capacity)
    duration = configured_slot_duration()
    try:
        with transaction.atomic():
            slot = SurveySlot.objects.create(
                starts_at=starts_at, ends_at=starts_at + duration,
                capacity=capacity, is_open=is_open, created_by=actor,
            )
    except (OverflowError, ValueError) as exc:
        raise ValidationError({"starts_at": ["The survey time is outside the supported date range."]}) from exc
    except IntegrityError as exc:
        raise SurveySlotConflict("SLOT_TIME_TAKEN", "A survey slot already starts at this time.") from exc
    record_audit_event(
        actor=actor, resource_type="SurveySlot", resource_id=slot.pk,
        action="SURVEY_SLOT_CREATED", before_data={}, after_data=_snapshot(slot),
        metadata={"version": slot.version},
    )
    return slot


@transaction.atomic
def update_slot(*, public_id, expected_version, actor, **data):
    _require_staff(actor)
    try:
        slot = SurveySlot.objects.select_for_update().get(public_id=public_id)
    except SurveySlot.DoesNotExist as exc:
        raise Http404("Survey slot not found.") from exc
    if isinstance(expected_version, bool) or not isinstance(expected_version, int) or expected_version < 0:
        raise ValidationError({"expected_version": ["Enter the version shown on the slot."]})
    if slot.version != expected_version:
        raise SurveySlotConflict("SLOT_CHANGED", "This slot changed. Reload it before saving.")
    changes = {field: value for field, value in data.items() if value != getattr(slot, field)}
    if not changes:
        return slot
    if "capacity" in changes:
        _validate_capacity(changes["capacity"])

    booked_count = slot.bookings.exclude(status=SurveyBooking.Status.CANCELLED).count()
    if "starts_at" in changes and booked_count:
        raise SurveySlotConflict("SLOT_HAS_BOOKINGS", "A booked slot's time cannot be changed.")
    if "capacity" in changes and changes["capacity"] < booked_count:
        raise SurveySlotConflict("SLOT_CAPACITY_TOO_LOW", "Capacity cannot be lower than existing bookings.")
    if "starts_at" in changes:
        _validate_start(changes["starts_at"])
        duration = configured_slot_duration()
        try:
            changes["ends_at"] = changes["starts_at"] + duration
        except OverflowError as exc:
            raise ValidationError({"starts_at": ["The survey time is outside the supported date range."]}) from exc
    if changes.get("is_open") and slot.starts_at <= timezone.now() and "starts_at" not in changes:
        raise ValidationError({"is_open": ["A past slot cannot be reopened."]})

    before = _snapshot(slot)
    for field, value in changes.items():
        setattr(slot, field, value)
    slot.version += 1
    try:
        with transaction.atomic():
            slot.save(update_fields=[*changes, "version", "updated_at"])
    except IntegrityError as exc:
        raise SurveySlotConflict("SLOT_TIME_TAKEN", "A survey slot already starts at this time.") from exc
    record_audit_event(
        actor=actor, resource_type="SurveySlot", resource_id=slot.pk,
        action="SURVEY_SLOT_CHANGED", before_data=before, after_data=_snapshot(slot),
        metadata={"version": slot.version},
    )
    return slot
