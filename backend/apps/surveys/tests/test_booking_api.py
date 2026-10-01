import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from unittest.mock import patch
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.core import mail, signing
from django.core.cache import cache
from django.db import close_old_connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.models import AuditEvent
from apps.communications.email import PermanentEmailError, render_email
from apps.communications.models import EmailOutbox
from apps.communications.services import process_one_email
from apps.orders.logging import RedactGuestTrackingToken
from apps.orders.models import Order
from apps.surveys.booking_services import book_survey
from apps.surveys.models import SurveyBooking, SurveySlot
from apps.surveys.tests.test_slot_api import future_start, make_booking
from apps.surveys.tracking import GUEST_TRACKING_SALT


BOOKINGS_URL = "/api/v1/surveys/bookings/"
BOOKING_SETTINGS = override_settings(
    SURVEY_LAHORE_SERVICE_AREAS='["Approved test area"]',
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)


def make_slot(*, days=7, capacity=1):
    start = future_start(days)
    return SurveySlot.objects.create(starts_at=start, ends_at=start + timedelta(hours=1), capacity=capacity)


def booking_data(slot):
    return {
        "slot_public_id": str(slot.public_id), "customer_name": "Survey Customer",
        "customer_email": "survey@example.com", "customer_phone": "03001234567",
        "site_address_line1": "Private test street", "site_area": "Approved test area",
        "site_city": "Lahore", "needs_description": "Review cameras purchased elsewhere.",
    }


@BOOKING_SETTINGS
class SurveyBookingApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.customer = get_user_model().objects.create_user(
            email="survey-account@example.com", password="test-password", full_name="Customer",
        )

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.slot = make_slot()
        self.data = booking_data(self.slot)
        self.key = uuid.uuid4()

    def post(self, data=None, key=None):
        return self.client.post(BOOKINGS_URL, data or self.data, format="json",
                                HTTP_IDEMPOTENCY_KEY=str(key or self.key))

    def test_guest_confirmation_email_and_uncertain_response_retry(self):
        first = self.post()
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(first.data["status"], "confirmed")
        self.assertEqual(first.data["booking_fee"], "0.00")
        self.assertEqual(first.data["service_type"], "site_survey")
        self.assertIn("Installation is quoted", first.data["installation_notice"])
        self.assertTrue(first.data["slot"]["starts_at"].endswith("+05:00"))
        self.assertNotIn("capacity", first.data["slot"])
        self.assertEqual(len(mail.outbox), 0, "Booking must queue email without sending during the request")
        booking = SurveyBooking.objects.get()
        self.assertIsNone(booking.user_id)
        self.assertIsNone(booking.related_order_id)
        self.assertFalse(Order.objects.exists())
        self.assertEqual(booking.site_address_line2, "")
        email = EmailOutbox.objects.get()
        self.assertEqual((email.event_type, email.survey_booking_id, email.status),
                         ("SURVEY_CONFIRMED", booking.pk, "pending"))
        self.assertEqual(AuditEvent.objects.get().action, "SURVEY_BOOKING_CONFIRMED")
        for key in ("request_fingerprint", "idempotency_key", "guest_link_nonce", "internal_notes", "user"):
            self.assertNotIn(key, first.data)
        for header, value in (("Cache-Control", "private, no-store"), ("Referrer-Policy", "no-referrer"),
                              ("X-Robots-Tag", "noindex, nofollow")):
            self.assertEqual(first[header], value)

        # The client lost the first response. A now-closed slot and changed business
        # configuration must not prevent recovery of the committed booking.
        SurveySlot.objects.filter(pk=self.slot.pk).update(is_open=False)
        with override_settings(SURVEY_LAHORE_SERVICE_AREAS=None):
            retry = self.post()
        self.assertEqual(retry.status_code, 200, retry.data)
        self.assertEqual(retry.data, first.data)
        self.assertEqual((SurveyBooking.objects.count(), EmailOutbox.objects.count(), AuditEvent.objects.count()), (1, 1, 1))
        self.assertEqual(process_one_email(), "sent")
        self.assertIn(booking.reference, mail.outbox[0].body)
        self.assertIn("free Lahore site survey", mail.outbox[0].body)
        self.assertIn("Installation is quoted and scheduled afterward", mail.outbox[0].body)
        self.assertIn(first.data["guest_tracking_url"], mail.outbox[0].body)
        self.assertIn("Asia/Karachi", mail.outbox[0].body)

    def test_signed_in_customer_is_associated_without_order_or_guest_link(self):
        token = RefreshToken.for_user(self.customer).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.post()
        self.assertEqual(response.status_code, 201, response.data)
        booking = SurveyBooking.objects.get()
        self.assertEqual(booking.user_id, self.customer.pk)
        self.assertIsNone(booking.related_order_id)
        self.assertIsNone(response.data["guest_tracking_url"])
        private_token = signing.Signer(salt=GUEST_TRACKING_SALT).sign_object(
            {"public_id": str(booking.public_id), "nonce": str(booking.guest_link_nonce)},
        )
        self.assertEqual(self.client.get(f"/api/v1/surveys/track/{private_token}/").status_code, 404)
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(process_one_email(), "sent")
        self.assertNotIn("/api/v1/surveys/track/", mail.outbox[0].body)

    def test_city_and_approved_area_both_required_and_configuration_fails_closed(self):
        for change, field in (({"site_city": "Islamabad"}, "site_city"),
                              ({"site_area": "Unapproved test area"}, "site_area"),
                              ({"site_area": ""}, "site_area")):
            response = self.post({**self.data, **change})
            self.assertEqual(response.status_code, 400, response.data)
            self.assertIn(field, response.data["error"]["fields"])
        for config in (None, "[]", "not json", '[""]', '{"area":"Approved test area"}'):
            with self.subTest(config=config), override_settings(SURVEY_LAHORE_SERVICE_AREAS=config):
                response = self.post()
                self.assertEqual(response.status_code, 503, response.data)
                self.assertEqual(response.data["error"]["code"], "SURVEY_NOT_CONFIGURED")
        self.assertFalse(SurveyBooking.objects.exists())
        self.assertFalse(EmailOutbox.objects.exists())

    def test_declared_city_and_area_match_ignore_case_and_surrounding_spaces(self):
        response = self.post({**self.data, "site_city": "  lahore  ", "site_area": "  APPROVED TEST AREA  "})
        self.assertEqual(response.status_code, 201, response.data)
        booking = SurveyBooking.objects.get()
        self.assertEqual((booking.site_city, booking.site_area), ("lahore", "APPROVED TEST AREA"))

    def test_unknown_fields_and_missing_uuid_key_are_rejected(self):
        for field in ("related_order", "user", "status", "internal_notes", "booking_fee"):
            response = self.post({**self.data, field: "unsupported"})
            self.assertEqual(response.status_code, 400, response.data)
            self.assertIn(field, response.data["error"]["fields"])
        for header in ({}, {"HTTP_IDEMPOTENCY_KEY": "invalid"}):
            response = self.client.post(BOOKINGS_URL, self.data, format="json", **header)
            self.assertEqual(response.status_code, 400, response.data)
            self.assertIn("idempotency_key", response.data["error"]["fields"])
        self.assertFalse(SurveyBooking.objects.exists())

    def test_key_reuse_with_different_body_or_identity_conflicts(self):
        self.assertEqual(self.post().status_code, 201)
        response = self.post({**self.data, "needs_description": "Different survey"})
        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(response.data["error"]["code"], "IDEMPOTENCY_CONFLICT")
        self.client.force_authenticate(user=self.customer)
        response = self.post()
        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(response.data["error"]["code"], "IDEMPOTENCY_CONFLICT")
        self.assertEqual(SurveyBooking.objects.count(), 1)

    def test_closed_past_missing_and_full_slots_do_not_book(self):
        for changes in ({"is_open": False}, {"is_open": True, "starts_at": timezone.now() - timedelta(minutes=1)}):
            SurveySlot.objects.filter(pk=self.slot.pk).update(**changes)
            response = self.post()
            self.assertEqual(response.status_code, 409, response.data)
            self.assertEqual(response.data["error"]["code"], "SURVEY_SLOT_UNAVAILABLE")
        missing = self.post({**self.data, "slot_public_id": str(uuid.uuid4())})
        self.assertEqual(missing.status_code, 409, missing.data)
        SurveySlot.objects.filter(pk=self.slot.pk).update(starts_at=future_start())
        existing = make_booking(self.slot, status="completed")
        full = self.post()
        self.assertEqual(full.status_code, 409, full.data)
        existing.status = "cancelled"
        existing.save(update_fields=["status"])
        self.assertEqual(self.post().status_code, 201)
        self.assertEqual(self.client.get("/api/v1/surveys/slots/").data["count"], 0)

    def test_guest_link_privacy_scope_revocation_and_log_redaction(self):
        response = self.post()
        path = urlsplit(response.data["guest_tracking_url"]).path
        tracking = self.client.get(path)
        self.assertEqual(tracking.status_code, 200, tracking.data)
        self.assertEqual(set(tracking.data), {"reference", "status", "slot", "site_area", "site_city", "installation_notice"})
        self.assertNotIn(self.data["site_address_line1"], str(tracking.data))
        self.assertNotIn(self.data["customer_email"], str(tracking.data))
        self.assertEqual(tracking["Cache-Control"], "private, no-store")
        self.assertEqual(self.client.patch(path, {}, format="json").status_code, 405)
        booking = SurveyBooking.objects.get()
        for token in (booking.reference, "forged", signing.Signer(salt="octacam.orders.guest-tracking").sign_object(
            {"public_id": str(booking.public_id), "nonce": str(booking.guest_link_nonce)},
        )):
            self.assertEqual(self.client.get(f"/api/v1/surveys/track/{token}/").status_code, 404)
        record = logging.LogRecord("test", logging.INFO, "", 0, "GET %s", (path,), None)
        RedactGuestTrackingToken().filter(record)
        self.assertIn("[REDACTED]", record.getMessage())
        self.assertNotIn(path, record.getMessage())
        booking.guest_link_nonce = uuid.uuid4()
        booking.save(update_fields=["guest_link_nonce"])
        self.assertEqual(self.client.get(path).status_code, 404)

    def test_cookie_alone_does_not_associate_account_and_csrf_is_required(self):
        client = APIClient(enforce_csrf_checks=True)
        client.cookies["octacam_refresh"] = str(RefreshToken.for_user(self.customer))
        denied = client.post(BOOKINGS_URL, self.data, format="json", HTTP_IDEMPOTENCY_KEY=str(self.key))
        self.assertEqual(denied.status_code, 403, denied.json())
        csrf = client.get("/api/v1/auth/csrf/").data["csrfToken"]
        response = client.post(BOOKINGS_URL, self.data, format="json", HTTP_IDEMPOTENCY_KEY=str(self.key), HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNone(SurveyBooking.objects.get().user_id)

    def test_outbox_failure_rolls_back_booking_and_audit(self):
        with patch("apps.surveys.booking_services.enqueue_email", side_effect=RuntimeError("outbox offline")):
            with self.assertRaises(RuntimeError):
                book_survey(data=self.data, idempotency_key=self.key, user=None)
        self.assertFalse(SurveyBooking.objects.exists())
        self.assertFalse(AuditEvent.objects.exists())
        self.assertFalse(EmailOutbox.objects.exists())

    def test_email_failure_keeps_booking_and_retry_uses_original_time(self):
        self.assertEqual(self.post().status_code, 201)
        original = self.slot.starts_at
        with patch("apps.communications.services.deliver_email", side_effect=OSError("SMTP offline")):
            self.assertEqual(process_one_email(), "failed")
        event = EmailOutbox.objects.get()
        self.assertEqual(SurveyBooking.objects.get().status, "confirmed")
        self.assertEqual(event.status, "failed")
        SurveySlot.objects.filter(pk=self.slot.pk).update(starts_at=original + timedelta(days=1), ends_at=original + timedelta(days=1, hours=1))
        EmailOutbox.objects.filter(pk=event.pk).update(next_attempt_at=timezone.now())
        self.assertEqual(process_one_email(), "sent")
        self.assertIn(original.strftime("%d %b %Y"), mail.outbox[0].body)
        self.assertEqual(EmailOutbox.objects.count(), 1)

    def test_malformed_email_event_and_wrong_recipient_fail_permanently(self):
        self.assertEqual(self.post().status_code, 201)
        event = EmailOutbox.objects.get()
        event.recipient = "other@example.com"
        with self.assertRaises(PermanentEmailError):
            render_email(event)
        event.recipient = self.data["customer_email"]
        event.context["starts_at"] = "not a date"
        with self.assertRaises(PermanentEmailError):
            render_email(event)


@BOOKING_SETTINGS
class SurveyBookingRaceTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.slot = make_slot()
        self.data = booking_data(self.slot)
        self.users = [get_user_model().objects.create_user(
            email=f"survey-race-{index}@example.com", password="test-password", full_name="Customer",
        ) for index in range(2)]

    def race(self, *, second_data, first_key, second_key, same_user=False):
        first_written, release_first, second_started, second_done = (Event() for _ in range(4))

        def request(data, key, user):
            client = APIClient()
            client.force_authenticate(user=user)
            return client.post(BOOKINGS_URL, data, format="json", HTTP_IDEMPOTENCY_KEY=str(key))

        def first():
            close_old_connections()
            try:
                with transaction.atomic():
                    response = request(self.data, first_key, self.users[0])
                    first_written.set()
                    if not release_first.wait(10):
                        raise AssertionError("Timed out releasing first booking")
                    return response.status_code, response.data
            finally:
                close_old_connections()

        def second():
            close_old_connections()
            try:
                second_started.set()
                response = request(second_data, second_key, self.users[0] if same_user else self.users[1])
                return response.status_code, response.data
            finally:
                second_done.set()
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            first_future = pool.submit(first)
            try:
                self.assertTrue(first_written.wait(10))
                second_future = pool.submit(second)
                self.assertTrue(second_started.wait(10))
                self.assertFalse(second_done.wait(0.2), "The second request bypassed the slot/key lock")
            finally:
                release_first.set()
            return first_future.result(timeout=10), second_future.result(timeout=10)

    def test_two_customers_compete_for_final_place(self):
        first, second = self.race(second_data=self.data, first_key=uuid.uuid4(), second_key=uuid.uuid4())
        self.assertEqual(first[0], 201, first[1])
        self.assertEqual(second[0], 409, second[1])
        self.assertEqual(second[1]["error"]["code"], "SURVEY_SLOT_UNAVAILABLE")
        self.assertEqual(SurveyBooking.objects.get().user_id, self.users[0].pk)
        self.assertEqual((SurveyBooking.objects.count(), EmailOutbox.objects.count(), AuditEvent.objects.count()), (1, 1, 1))

    def test_concurrent_retry_returns_same_confirmation(self):
        key = uuid.uuid4()
        first, second = self.race(second_data=self.data, first_key=key, second_key=key, same_user=True)
        self.assertEqual((first[0], second[0]), (201, 200))
        self.assertEqual(first[1], second[1])
        self.assertEqual((SurveyBooking.objects.count(), EmailOutbox.objects.count()), (1, 1))

    def test_same_key_with_different_slots_creates_only_one_booking(self):
        second_slot = make_slot(days=8)
        key = uuid.uuid4()
        first, second = self.race(second_data=booking_data(second_slot), first_key=key, second_key=key, same_user=True)
        self.assertEqual(first[0], 201, first[1])
        self.assertEqual(second[0], 409, second[1])
        self.assertEqual(second[1]["error"]["code"], "IDEMPOTENCY_CONFLICT")
        self.assertEqual((SurveyBooking.objects.count(), EmailOutbox.objects.count()), (1, 1))
