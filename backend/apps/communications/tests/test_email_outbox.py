from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.db import close_old_connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.models import AuditEvent
from apps.communications.models import EmailOutbox
from apps.communications.services import (
    claim_next_email, enqueue_email, finish_delivery, process_email_batch,
)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EmailOutboxTests(TestCase):
    def setUp(self):
        cache.clear()
        self.staff = get_user_model().objects.create_user(
            email="email-staff@example.com", password="test-password", full_name="Staff", is_staff=True,
        )
        self.customer = get_user_model().objects.create_user(
            email="email-customer@example.com", password="test-password", full_name="Customer",
        )
        self.client = APIClient()

    def event(self, *, key="order-123"):
        return enqueue_email(
            event_type=EmailOutbox.EventType.ORDER_PLACED,
            recipient="buyer@example.com", template_name="order_placed",
            context={"order_reference": "DEMO-123"}, dedupe_key=key,
        )

    def authorize(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")

    def test_enqueue_is_deduplicated_and_rolls_back_with_business_transaction(self):
        first = self.event()
        same = self.event()
        self.assertEqual(first.pk, same.pk)
        self.assertEqual(EmailOutbox.objects.count(), 1)
        with self.assertRaises(ValueError):
            enqueue_email(
                event_type=EmailOutbox.EventType.SURVEY_CONFIRMED,
                recipient="other@example.com", template_name="survey_confirmed",
                context={}, dedupe_key="order-123",
            )
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                self.event(key="rolled-back")
                raise RuntimeError("Business transaction failed")
        self.assertFalse(EmailOutbox.objects.filter(dedupe_key="rolled-back").exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_failed_delivery_schedules_retry_and_staff_can_retry_immediately(self):
        message = self.event()
        with patch("apps.communications.services.deliver_email", side_effect=OSError("provider unavailable")):
            self.assertEqual(process_email_batch(), ["failed"])
        message.refresh_from_db()
        self.assertEqual(message.status, "failed")
        self.assertEqual(message.attempt_count, 1)
        self.assertGreater(message.next_attempt_at, timezone.now())
        self.assertEqual(message.last_error, "OSError")
        self.assertEqual(process_email_batch(), [])

        self.authorize(self.staff)
        listing = self.client.get("/api/v1/staff/communications/emails/?status=failed")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data["count"], 1)
        self.assertNotIn("context", listing.data["results"][0])
        retry = self.client.post(f"/api/v1/staff/communications/emails/{message.pk}/retry/")
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.data["status"], "pending")
        self.assertEqual(AuditEvent.objects.get().action, "EMAIL_RETRY_REQUESTED")

        with patch("apps.communications.services.deliver_email") as deliver:
            self.assertEqual(process_email_batch(), ["sent"])
            deliver.assert_called_once()
        message.refresh_from_db()
        self.assertEqual(message.status, "sent")
        self.assertEqual(message.attempt_count, 2)
        self.assertIsNone(message.next_attempt_at)
        self.assertEqual(message.last_error, "")
        self.assertIsNotNone(message.sent_at)
        self.assertEqual(process_email_batch(), [])
        self.assertEqual(self.client.post(f"/api/v1/staff/communications/emails/{message.pk}/retry/").status_code, 400)

    def test_worker_bounds_automatic_retries_and_preserves_final_failure(self):
        message = self.event()
        with override_settings(EMAIL_OUTBOX_MAX_ATTEMPTS=2):
            with patch("apps.communications.services.deliver_email", side_effect=ConnectionError("offline")):
                self.assertEqual(process_email_batch(), ["failed"])
                EmailOutbox.objects.filter(pk=message.pk).update(next_attempt_at=timezone.now())
                self.assertEqual(process_email_batch(), ["failed"])
        message.refresh_from_db()
        self.assertEqual(message.attempt_count, 2)
        self.assertEqual(message.status, "failed")
        self.assertIsNone(message.next_attempt_at)
        self.assertEqual(message.last_error, "ConnectionError")
        self.assertEqual(process_email_batch(), [])

    def test_staff_visibility_and_retry_permissions(self):
        message = self.event()
        EmailOutbox.objects.filter(pk=message.pk).update(status="failed", next_attempt_at=None)
        for user, expected in ((None, 401), (self.customer, 403)):
            with self.subTest(user=user):
                self.client.credentials()
                if user:
                    self.authorize(user)
                self.assertEqual(self.client.get("/api/v1/staff/communications/emails/").status_code, expected)
                self.assertEqual(self.client.post(
                    f"/api/v1/staff/communications/emails/{message.pk}/retry/",
                ).status_code, expected)
        message.refresh_from_db()
        self.assertEqual(message.status, "failed")

    def test_expired_claim_can_be_reclaimed_but_old_claim_cannot_finish(self):
        message = self.event()
        first = claim_next_email()
        self.assertEqual(first.pk, message.pk)
        self.assertIsNone(claim_next_email())
        EmailOutbox.objects.filter(pk=message.pk).update(locked_until=timezone.now() - timedelta(seconds=1))
        second = claim_next_email()
        self.assertNotEqual(first.claim_token, second.claim_token)
        self.assertFalse(finish_delivery(message_id=message.pk, claim_token=first.claim_token))
        self.assertTrue(finish_delivery(message_id=message.pk, claim_token=second.claim_token))
        message.refresh_from_db()
        self.assertEqual(message.status, "sent")
        self.assertEqual(message.attempt_count, 1)

    def test_once_command_processes_one_batch(self):
        message = self.event()
        output = StringIO()
        with patch("apps.communications.services.deliver_email") as deliver:
            call_command("process_email_outbox", "--once", stdout=output)
            deliver.assert_called_once()
        self.assertIn("1 sent", output.getvalue())
        message.refresh_from_db()
        self.assertEqual(message.status, "sent")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EmailClaimConcurrencyTests(TransactionTestCase):
    def test_parallel_workers_claim_one_row_once(self):
        message = EmailOutbox.objects.create(
            event_type=EmailOutbox.EventType.ORDER_PLACED,
            recipient="buyer@example.com", template_name="order_placed", context={}, dedupe_key="one-event",
        )
        barrier = Barrier(2)

        def claim():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                result = claim_next_email()
                return result.pk if result else None
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            claimed = list(pool.map(lambda _: claim(), range(2)))
        self.assertEqual(sorted(claimed, key=lambda value: value is None), [message.pk, None])
