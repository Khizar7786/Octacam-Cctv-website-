import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.services import record_audit_event

from .email import PermanentEmailError, deliver_email
from .models import EmailOutbox


def enqueue_email(*, event_type, recipient, template_name, context, dedupe_key, order=None):
    """Call within the business transaction; the worker sends after commit."""
    message, created = EmailOutbox.objects.get_or_create(
        dedupe_key=dedupe_key,
        defaults={
            "event_type": event_type,
            "order": order,
            "recipient": recipient,
            "template_name": template_name,
            "context": context,
        },
    )
    if not created and (message.event_type != event_type or message.recipient != recipient or message.order_id != (order.pk if order else None)):
        raise ValueError("Email dedupe key belongs to a different event")
    return message


@transaction.atomic
def claim_next_email():
    now = timezone.now()
    message = (
        EmailOutbox.objects.filter(
            status__in=[EmailOutbox.Status.PENDING, EmailOutbox.Status.FAILED],
            next_attempt_at__lte=now,
        )
        .filter(Q(locked_until__isnull=True) | Q(locked_until__lte=now))
        .select_for_update(skip_locked=True)
        .order_by("next_attempt_at", "id")
        .first()
    )
    if message is None:
        return None
    message.claim_token = uuid.uuid4()
    message.locked_until = now + timedelta(seconds=settings.EMAIL_OUTBOX_CLAIM_SECONDS)
    message.save(update_fields=["claim_token", "locked_until"])
    return message


@transaction.atomic
def finish_delivery(*, message_id, claim_token, error=None, permanent=False):
    message = EmailOutbox.objects.select_for_update().get(pk=message_id)
    if message.claim_token != claim_token:
        return False
    message.attempt_count += 1
    message.claim_token = None
    message.locked_until = None
    if error is None:
        message.status = EmailOutbox.Status.SENT
        message.sent_at = timezone.now()
        message.next_attempt_at = None
        message.last_error = ""
    else:
        message.status = EmailOutbox.Status.FAILED
        message.last_error = (
            f"{type(error).__name__}: {error}" if isinstance(error, PermanentEmailError)
            else type(error).__name__
        )[:300]
        if permanent or message.attempt_count >= settings.EMAIL_OUTBOX_MAX_ATTEMPTS:
            message.next_attempt_at = None
        else:
            delay = min(60 * (2 ** (message.attempt_count - 1)), 3600)
            message.next_attempt_at = timezone.now() + timedelta(seconds=delay)
    if message.event_type == EmailOutbox.EventType.PASSWORD_RESET and (error is None or permanent):
        message.context = {}
    message.save(update_fields=[
        "attempt_count", "claim_token", "locked_until", "status", "sent_at", "next_attempt_at", "last_error",
        "context",
    ])
    return True


def process_one_email():
    message = claim_next_email()
    if message is None:
        return None
    try:
        deliver_email(message)
    except Exception as exc:
        finish_delivery(
            message_id=message.pk, claim_token=message.claim_token,
            error=exc, permanent=isinstance(exc, PermanentEmailError),
        )
        return "failed"
    finish_delivery(message_id=message.pk, claim_token=message.claim_token)
    return "sent"


def process_email_batch(*, limit=20):
    outcomes = []
    for _ in range(limit):
        outcome = process_one_email()
        if outcome is None:
            break
        outcomes.append(outcome)
    return outcomes


@transaction.atomic
def retry_email(*, email_id, actor):
    message = get_object_or_404(EmailOutbox.objects.select_for_update(), pk=email_id)
    if message.status != EmailOutbox.Status.FAILED or (
        message.locked_until is not None and message.locked_until > timezone.now()
    ):
        raise ValidationError({"status": ["Only a failed, unclaimed email can be retried."]})
    if message.event_type == EmailOutbox.EventType.PASSWORD_RESET and message.last_error.startswith("PermanentEmailError"):
        raise ValidationError({"status": ["This reset request expired or is no longer valid. Request a new link."]})
    message.status = EmailOutbox.Status.PENDING
    message.next_attempt_at = timezone.now()
    message.claim_token = None
    message.locked_until = None
    message.save(update_fields=["status", "next_attempt_at", "claim_token", "locked_until"])
    record_audit_event(
        actor=actor, resource_type="EmailOutbox", resource_id=message.pk,
        action="EMAIL_RETRY_REQUESTED", before_data={"status": "failed"}, after_data={"status": "pending"},
    )
    return message
