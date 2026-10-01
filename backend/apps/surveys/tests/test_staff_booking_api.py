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
from apps.orders.models import Order
from apps.surveys.management_services import reschedule_survey, transition_survey, update_survey_notes
from apps.surveys.models import SurveyBooking, SurveySlot
from apps.surveys.selectors import staff_slots
from apps.surveys.tests.test_booking_api import booking_data, make_slot
from apps.surveys.tests.test_slot_api import future_start, make_booking
from apps.surveys.tracking import GUEST_TRACKING_SALT, build_guest_tracking_url


STAFF_BOOKINGS = "/api/v1/staff/surveys/bookings/"
SURVEY_SETTINGS = override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    SURVEY_SLOT_DURATION_MINUTES="60",
    SURVEY_LAHORE_SERVICE_AREAS='["Approved test area"]',
)


@SURVEY_SETTINGS
class StaffSurveyBookingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(
            email="booking-staff@example.com", password="test-password", full_name="Staff", is_staff=True,
        )
        cls.customer = get_user_model().objects.create_user(
            email="booking-customer@example.com", password="test-password", full_name="Customer",
        )

    def setUp(self):
        cache.clear()
        self.slot = make_slot()
        self.booking = make_booking(self.slot)
        self.detail = f"{STAFF_BOOKINGS}{self.booking.public_id}/"
        self.tracking = urlsplit(build_guest_tracking_url(self.booking)).path
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(self.staff).access_token}")

    def command(self, suffix, data):
        return self.client.post(f"{self.detail}{suffix}/", data, format="json")

    def occupancy(self, slot):
        return staff_slots().get(pk=slot.pk).booked_count

    def test_staff_only_permissions_on_every_booking_route(self):
        routes = [
            ("get", STAFF_BOOKINGS, None), ("get", self.detail, None),
            ("get", f"{self.detail}history/", None),
            ("post", f"{self.detail}reschedule/", {"expected_version": 0, "slot_public_id": str(self.slot.public_id)}),
            ("post", f"{self.detail}transition/", {"expected_version": 0, "status": "cancelled"}),
            ("patch", f"{self.detail}notes/", {"expected_version": 0, "internal_notes": "private"}),
        ]
        for user, expected in ((None, 401), (self.customer, 403)):
            client = APIClient()
            if user:
                client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
            for method, path, data in routes:
                with self.subTest(user=user, path=path):
                    response = getattr(client, method)(path, data, format="json")
                    self.assertEqual(response.status_code, expected, response.data)
                    self.assertEqual(response["Cache-Control"], "private, no-store")
        self.booking.refresh_from_db()
        self.assertEqual((self.booking.status, self.booking.version, self.booking.internal_notes), ("confirmed", 0, ""))
        self.assertFalse(AuditEvent.objects.exists())
        self.assertFalse(EmailOutbox.objects.exists())
        self.staff.is_active = False
        self.staff.save(update_fields=["is_active"])
        self.assertEqual(self.client.get(self.detail).status_code, 401)

    def test_staff_inspection_filters_and_private_note_history(self):
        note = "Internal access instructions; never send to customer."
        response = self.client.patch(f"{self.detail}notes/", {
            "expected_version": 0, "internal_notes": note,
        }, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual((response.data["internal_notes"], response.data["version"]), (note, 1))
        detail = self.client.get(self.detail)
        self.assertEqual(detail.data["customer_email"], self.booking.customer_email)
        self.assertEqual(detail.data["needs_description"], self.booking.needs_description)
        self.assertNotIn("guest_link_nonce", detail.data)
        self.assertNotIn("idempotency_key", detail.data)
        matching = self.client.get(STAFF_BOOKINGS, {"q": self.booking.reference, "status": "confirmed"})
        self.assertEqual(matching.data["count"], 1)
        self.assertEqual(self.client.get(STAFF_BOOKINGS, {"status": "cancelled"}).data["count"], 0)
        self.assertEqual(self.client.get(STAFF_BOOKINGS, {"status": "invented"}).status_code, 400)
        self.assertEqual(self.client.get(f"{STAFF_BOOKINGS}{uuid.uuid4()}/").status_code, 404)
        history = self.client.get(f"{self.detail}history/")
        self.assertEqual(history.data["count"], 1)
        event = history.data["results"][0]
        self.assertEqual(event["action"], "SURVEY_BOOKING_NOTES_UPDATED")
        self.assertEqual(event["actor_email"], self.staff.email)
        self.assertEqual(event["after_data"]["internal_notes"], note)
        self.assertFalse(EmailOutbox.objects.exists())
        # Updating notes after completion/cancellation remains useful to support.
        self.command("transition", {"expected_version": 1, "status": "cancelled"})
        cleared = self.client.patch(f"{self.detail}notes/", {"expected_version": 2, "internal_notes": ""}, format="json")
        self.assertEqual(cleared.status_code, 200, cleared.data)
        self.assertEqual(EmailOutbox.objects.count(), 1)

    def test_public_tracking_is_scoped_read_only_and_excludes_all_internal_data(self):
        self.client.patch(f"{self.detail}notes/", {"expected_version": 0, "internal_notes": "Secret staff note"}, format="json")
        other = make_booking(make_slot(days=8))
        public = APIClient()
        result = public.get(self.tracking)
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(set(result.data), {"reference", "status", "slot", "site_area", "site_city", "installation_notice"})
        self.assertEqual(set(result.data["slot"]), {"public_id", "starts_at", "ends_at"})
        for secret in (
            "Secret staff note", self.booking.customer_email, self.booking.customer_phone,
            self.booking.site_address_line1, self.booking.needs_description, self.staff.email, other.reference,
        ):
            self.assertNotIn(secret, str(result.data))
        self.assertEqual(result["Cache-Control"], "private, no-store")
        self.assertEqual(result["Referrer-Policy"], "no-referrer")
        self.assertEqual(result["X-Robots-Tag"], "noindex, nofollow")
        for method in ("post", "patch", "delete"):
            self.assertEqual(getattr(public, method)(self.tracking, {}, format="json").status_code, 405)
        token = self.tracking.split("/")[-2]
        payload = signing.Signer(salt=GUEST_TRACKING_SALT).unsign_object(token)
        payload["public_id"] = str(other.public_id)
        # Even a valid signature cannot mix another booking ID with this nonce.
        mixed = signing.Signer(salt=GUEST_TRACKING_SALT).sign_object(payload)
        invalid = public.get(f"/api/v1/surveys/track/{mixed}/")
        forged = public.get("/api/v1/surveys/track/forged/")
        self.assertEqual((invalid.status_code, forged.status_code), (404, 404))
        self.assertEqual(invalid.data, forged.data)
        self.assertEqual(invalid["Cache-Control"], "private, no-store")
        self.booking.user = self.customer
        self.booking.save(update_fields=["user"])
        self.assertEqual(public.get(self.tracking).status_code, 404)

    def test_booking_receipt_retries_and_public_availability_exclude_internal_information(self):
        public = APIClient()
        destination = make_slot(days=8)
        key = str(uuid.uuid4())
        data = booking_data(destination)
        created = public.post("/api/v1/surveys/bookings/", data, format="json", HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(created.status_code, 201, created.data)
        detail = f"{STAFF_BOOKINGS}{created.data['public_id']}/"
        self.client.patch(f"{detail}notes/", {"expected_version": 0, "internal_notes": "Secret staff note"}, format="json")
        receipt = public.post("/api/v1/surveys/bookings/", data, format="json", HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(receipt.status_code, 200, receipt.data)
        self.assertNotIn("Secret staff note", str(receipt.data))
        for field in ("internal_notes", "version", "guest_link_nonce", "idempotency_key", "request_fingerprint", "history"):
            self.assertNotIn(field, receipt.data)
        available = make_slot(days=9)
        slots = public.get("/api/v1/surveys/slots/")
        self.assertEqual(slots.data["count"], 1)
        self.assertEqual(set(slots.data["results"][0]), {"public_id", "starts_at", "ends_at"})
        self.assertEqual(slots.data["results"][0]["public_id"], str(available.public_id))

    def test_rescheduling_moves_capacity_records_both_times_and_updates_guest_link(self):
        destination = make_slot(days=8)
        response = self.command("reschedule", {"expected_version": 0, "slot_public_id": str(destination.public_id)})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual((self.occupancy(self.slot), self.occupancy(destination)), (0, 1))
        self.booking.refresh_from_db()
        self.assertEqual((self.booking.slot_id, self.booking.version), (destination.pk, 1))
        self.assertEqual(self.booking.scheduled_starts_at, destination.starts_at)
        event = AuditEvent.objects.get()
        self.assertEqual(event.before_data["slot_public_id"], str(self.slot.public_id))
        self.assertEqual(event.after_data["slot_public_id"], str(destination.public_id))
        self.assertEqual(event.actor_id, self.staff.pk)
        guest = APIClient().get(self.tracking)
        self.assertEqual(guest.data["status"], "confirmed")
        self.assertEqual(guest.data["slot"]["public_id"], str(destination.public_id))
        self.assertTrue(guest.data["slot"]["starts_at"].endswith("+05:00"))
        self.assertEqual(EmailOutbox.objects.get().event_type, "SURVEY_CHANGED")
        stale = self.command("reschedule", {"expected_version": 0, "slot_public_id": str(destination.public_id)})
        self.assertEqual(stale.status_code, 409, stale.data)
        self.assertEqual(stale.data["error"]["code"], "BOOKING_CHANGED")
        same = self.command("reschedule", {"expected_version": 1, "slot_public_id": str(destination.public_id)})
        self.assertEqual(same.status_code, 200, same.data)
        self.assertEqual((AuditEvent.objects.count(), EmailOutbox.objects.count()), (1, 1))

    def test_unavailable_destinations_preserve_original_booking_and_capacity(self):
        closed, past, full = make_slot(days=8), make_slot(days=-1), make_slot(days=9)
        closed.is_open = False
        closed.save(update_fields=["is_open"])
        make_booking(full, status="completed")
        for destination in (closed.public_id, past.public_id, full.public_id, uuid.uuid4()):
            with self.subTest(destination=destination):
                response = self.command("reschedule", {"expected_version": 0, "slot_public_id": str(destination)})
                self.assertEqual(response.status_code, 409, response.data)
                self.assertEqual(response.data["error"]["code"], "SURVEY_SLOT_UNAVAILABLE")
        self.booking.refresh_from_db()
        self.assertEqual((self.booking.slot_id, self.booking.version, self.occupancy(self.slot)), (self.slot.pk, 0, 1))
        self.assertFalse(AuditEvent.objects.exists())
        self.assertFalse(EmailOutbox.objects.exists())

    def test_cancellation_releases_one_place_and_keeps_historical_time(self):
        original = self.booking.scheduled_starts_at
        first = self.command("transition", {"expected_version": 0, "status": "cancelled"})
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(self.occupancy(self.slot), 0)
        stale = self.command("transition", {"expected_version": 0, "status": "cancelled"})
        self.assertEqual(stale.status_code, 409, stale.data)
        again = self.command("transition", {"expected_version": 1, "status": "cancelled"})
        self.assertEqual(again.status_code, 200, again.data)
        self.assertEqual((AuditEvent.objects.count(), EmailOutbox.objects.count()), (1, 1))
        self.assertEqual(EmailOutbox.objects.get().event_type, "SURVEY_CANCELLED")
        changed_slot = self.client.patch(f"/api/v1/staff/surveys/slots/{self.slot.public_id}/", {
            "expected_version": 0, "starts_at": future_start(8).isoformat(),
        }, format="json")
        self.assertEqual(changed_slot.status_code, 200, changed_slot.data)
        tracked = APIClient().get(self.tracking)
        self.assertEqual(tracked.data["status"], "cancelled")
        self.assertEqual(tracked.data["slot"]["starts_at"], original.isoformat())
        self.assertEqual(process_one_email(), "sent")
        self.assertIn(original.strftime("%d %b %Y"), mail.outbox[0].body)
        self.assertNotIn(future_start(8).strftime("%d %b %Y"), mail.outbox[0].body)

    def test_completed_bookings_count_and_terminal_states_cannot_reopen_or_move(self):
        completed = self.command("transition", {"expected_version": 0, "status": "completed"})
        self.assertEqual(completed.status_code, 200, completed.data)
        self.assertEqual(self.occupancy(self.slot), 1)
        self.assertEqual(APIClient().get(self.tracking).data["status"], "completed")
        self.assertEqual(EmailOutbox.objects.get().event_type, "SURVEY_CHANGED")
        self.assertEqual(self.command("transition", {"expected_version": 1, "status": "completed"}).status_code, 200)
        for terminal in ("completed", "cancelled"):
            SurveyBooking.objects.filter(pk=self.booking.pk).update(status=terminal)
            other_terminal = "cancelled" if terminal == "completed" else "completed"
            invalid = self.command("transition", {"expected_version": 1, "status": other_terminal})
            self.assertEqual(invalid.status_code, 409, invalid.data)
            move = self.command("reschedule", {"expected_version": 1, "slot_public_id": str(make_slot(days=8 if terminal == "completed" else 9).public_id)})
            self.assertEqual(move.status_code, 409, move.data)
        self.assertEqual(self.command("transition", {"expected_version": 1, "status": "confirmed"}).status_code, 400)
        self.assertEqual((AuditEvent.objects.count(), EmailOutbox.objects.count()), (1, 1))

    def test_validation_and_stale_notes_do_not_overwrite_staff_work(self):
        response = self.client.patch(f"{self.detail}notes/", {"expected_version": 0, "internal_notes": "first"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        stale = self.client.patch(f"{self.detail}notes/", {"expected_version": 0, "internal_notes": "lost update"}, format="json")
        self.assertEqual(stale.status_code, 409, stale.data)
        for data in ({"internal_notes": "x"}, {"expected_version": -1, "internal_notes": "x"},
                     {"expected_version": 1, "internal_notes": "x", "customer_email": "attacker@example.com"},
                     {"expected_version": 1, "internal_notes": "x" * 10001}):
            self.assertEqual(self.client.patch(f"{self.detail}notes/", data, format="json").status_code, 400)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.internal_notes, "first")
        self.assertEqual(AuditEvent.objects.count(), 1)

    def test_survey_changes_do_not_change_related_equipment_order(self):
        order = Order.objects.create(
            reference="OC-RELATED-SURVEY", customer_name="Customer", customer_email="survey@example.com",
            customer_phone="test-phone", delivery_address_line1="Private address", delivery_city="Lahore",
            delivery_province="Punjab", subtotal=0, tax_total=0, shipping_fee=0, shipping_tax_amount=0,
            grand_total=0, tax_rate_percent=0, shipping_taxable=False, idempotency_key=uuid.uuid4(), request_fingerprint="a" * 64,
        )
        self.booking.related_order = order
        self.booking.save(update_fields=["related_order"])
        inspected = self.client.get(self.detail)
        self.assertEqual(inspected.data["related_order"], {"public_id": str(order.public_id), "reference": order.reference})
        self.assertNotIn(order.reference, str(APIClient().get(self.tracking).data))
        self.command("reschedule", {"expected_version": 0, "slot_public_id": str(make_slot(days=8).public_id)})
        self.command("transition", {"expected_version": 1, "status": "cancelled"})
        order.refresh_from_db()
        self.assertEqual((order.status, order.payment_status, order.version), ("placed", "uncollected", 0))

    def test_transaction_failures_roll_back_booking_capacity_audit_and_outbox(self):
        destination = make_slot(days=8)
        for command in (
            lambda: reschedule_survey(public_id=self.booking.public_id, slot_public_id=destination.public_id, expected_version=0, actor=self.staff),
            lambda: transition_survey(public_id=self.booking.public_id, status="cancelled", expected_version=0, actor=self.staff),
            lambda: transition_survey(public_id=self.booking.public_id, status="completed", expected_version=0, actor=self.staff),
        ):
            with patch("apps.surveys.management_services.enqueue_email", side_effect=RuntimeError("outbox failed")):
                with self.assertRaises(RuntimeError):
                    command()
            self.booking.refresh_from_db()
            self.assertEqual((self.booking.status, self.booking.slot_id, self.booking.version), ("confirmed", self.slot.pk, 0))
            self.assertEqual((self.occupancy(self.slot), self.occupancy(destination)), (1, 0))
            self.assertFalse(AuditEvent.objects.exists())
            self.assertFalse(EmailOutbox.objects.exists())
        with patch("apps.surveys.management_services.record_audit_event", side_effect=RuntimeError("audit failed")):
            with self.assertRaises(RuntimeError):
                update_survey_notes(public_id=self.booking.public_id, internal_notes="private", expected_version=0, actor=self.staff)
        self.booking.refresh_from_db()
        self.assertEqual((self.booking.internal_notes, self.booking.version), ("", 0))

    def test_delayed_change_emails_use_event_snapshots_and_never_internal_notes(self):
        self.client.patch(f"{self.detail}notes/", {"expected_version": 0, "internal_notes": "Secret staff note"}, format="json")
        destination = make_slot(days=8)
        self.command("reschedule", {"expected_version": 1, "slot_public_id": str(destination.public_id)})
        changed = EmailOutbox.objects.get()
        with patch("apps.communications.services.deliver_email", side_effect=OSError("SMTP offline")):
            self.assertEqual(process_one_email(), "failed")
        self.assertEqual(APIClient().get(self.tracking).data["status"], "confirmed")
        self.command("reschedule", {"expected_version": 2, "slot_public_id": str(make_slot(days=9).public_id)})
        self.command("transition", {"expected_version": 3, "status": "completed"})
        subject, body = render_email(changed)
        self.assertIn(self.booking.reference, subject)
        self.assertIn(self.slot.starts_at.strftime("%d %b %Y"), body)
        self.assertIn(destination.starts_at.strftime("%d %b %Y"), body)
        self.assertNotIn(future_start(9).strftime("%d %b %Y"), body)
        self.assertNotIn("Secret staff note", body)
        completed = EmailOutbox.objects.order_by("id").last()
        self.assertIn("completed", render_email(completed)[1])
        changed.recipient = "another@example.com"
        with self.assertRaises(PermanentEmailError):
            render_email(changed)
        changed.recipient = self.booking.customer_email
        for malformed in ({"change": []}, {"after": {"status": "cancelled"}}, {"before": {"status": "confirmed", "starts_at": "invalid"}}):
            original = changed.context.copy()
            changed.context.update(malformed)
            with self.assertRaises(PermanentEmailError):
                render_email(changed)
            changed.context = original


@SURVEY_SETTINGS
class SurveyManagementRaceTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.staff = get_user_model().objects.create_user(
            email="race-booking-staff@example.com", password="test-password", full_name="Staff", is_staff=True,
        )
        self.source = make_slot(capacity=2)
        self.bookings = [make_booking(self.source) for _ in range(2)]
        self.destination = make_slot(days=8)

    def request(self, booking, suffix, data):
        client = APIClient()
        client.force_authenticate(user=self.staff)
        return client.post(f"{STAFF_BOOKINGS}{booking.public_id}/{suffix}/", data, format="json")

    def move(self, booking, destination):
        return self.request(booking, "reschedule", {"expected_version": 0, "slot_public_id": str(destination.public_id)})

    def race(self, first_call, second_call):
        written, release, started, done = (Event() for _ in range(4))

        def first():
            close_old_connections()
            try:
                with transaction.atomic():
                    response = first_call()
                    written.set()
                    if not release.wait(10):
                        raise AssertionError("Timed out releasing first survey change")
                    return response.status_code, response.data
            finally:
                close_old_connections()

        def second():
            close_old_connections()
            try:
                started.set()
                response = second_call()
                return response.status_code, response.data
            finally:
                done.set()
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            first_future = pool.submit(first)
            try:
                self.assertTrue(written.wait(10))
                second_future = pool.submit(second)
                self.assertTrue(started.wait(10))
                self.assertFalse(done.wait(0.2), "The competing request bypassed the capacity/booking lock")
            finally:
                release.set()
            return first_future.result(timeout=10), second_future.result(timeout=10)

    def test_two_reschedules_compete_for_destination_final_place(self):
        first, second = self.race(lambda: self.move(self.bookings[0], self.destination),
                                  lambda: self.move(self.bookings[1], self.destination))
        self.assertEqual(first[0], 200, first[1])
        self.assertEqual(second[0], 409, second[1])
        self.assertEqual(second[1]["error"]["code"], "SURVEY_SLOT_UNAVAILABLE")
        self.assertEqual(self.destination.bookings.exclude(status="cancelled").count(), 1)
        self.assertEqual(self.source.bookings.exclude(status="cancelled").count(), 1)
        self.assertEqual((AuditEvent.objects.count(), EmailOutbox.objects.count()), (1, 1))

    def test_concurrent_moves_of_same_booking_reject_stale_destination(self):
        other_destination = make_slot(days=9)
        first, second = self.race(lambda: self.move(self.bookings[0], self.destination),
                                  lambda: self.move(self.bookings[0], other_destination))
        self.assertEqual((first[0], second[0]), (200, 409))
        self.assertEqual(second[1]["error"]["code"], "BOOKING_CHANGED")
        self.assertEqual(other_destination.bookings.count(), 0)
        self.assertEqual((AuditEvent.objects.count(), EmailOutbox.objects.count()), (1, 1))

    def test_moves_in_opposite_directions_serialize_and_preserve_capacity(self):
        self.destination.capacity = 2
        self.destination.save(update_fields=["capacity"])
        other = make_booking(self.destination)
        first, second = self.race(lambda: self.move(self.bookings[0], self.destination), lambda: self.move(other, self.source))
        self.assertEqual((first[0], second[0]), (200, 200))
        self.assertEqual((self.source.bookings.count(), self.destination.bookings.count()), (2, 1))
        self.assertEqual((AuditEvent.objects.count(), EmailOutbox.objects.count()), (2, 2))

    def test_reschedule_competes_with_new_booking_using_same_slot_lock(self):
        def new_booking():
            return APIClient().post("/api/v1/surveys/bookings/", booking_data(self.destination),
                                    format="json", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        first, second = self.race(lambda: self.move(self.bookings[0], self.destination), new_booking)
        self.assertEqual((first[0], second[0]), (200, 409))
        self.assertEqual(second[1]["error"]["code"], "SURVEY_SLOT_UNAVAILABLE")
        self.assertEqual(SurveyBooking.objects.count(), 2)

    def test_concurrent_cancellation_and_rescheduling_cannot_change_terminal_booking(self):
        first, second = self.race(
            lambda: self.request(self.bookings[0], "transition", {"expected_version": 0, "status": "cancelled"}),
            lambda: self.move(self.bookings[0], self.destination),
        )
        self.assertEqual((first[0], second[0]), (200, 409))
        self.assertEqual(second[1]["error"]["code"], "BOOKING_CHANGED")
        self.assertEqual(self.destination.bookings.count(), 0)
        self.assertEqual((AuditEvent.objects.count(), EmailOutbox.objects.count()), (1, 1))

    def test_concurrent_cancellation_releases_only_one_place(self):
        cancel = lambda: self.request(self.bookings[0], "transition", {"expected_version": 0, "status": "cancelled"})
        first, second = self.race(cancel, cancel)
        self.assertEqual((first[0], second[0]), (200, 409))
        self.assertEqual(second[1]["error"]["code"], "BOOKING_CHANGED")
        self.assertEqual(self.source.bookings.exclude(status="cancelled").count(), 1)
        self.assertEqual((AuditEvent.objects.count(), EmailOutbox.objects.count()), (1, 1))

    def test_new_booking_waits_for_cancellation_then_uses_released_place(self):
        self.source.is_open = False
        self.source.save(update_fields=["is_open"])
        booking = make_booking(self.destination)
        def new_booking():
            return APIClient().post("/api/v1/surveys/bookings/", booking_data(self.destination),
                                    format="json", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        first, second = self.race(
            lambda: self.request(booking, "transition", {"expected_version": 0, "status": "cancelled"}),
            new_booking,
        )
        self.assertEqual((first[0], second[0]), (200, 201))
        self.assertEqual(self.destination.bookings.exclude(status="cancelled").count(), 1)
        self.assertEqual((AuditEvent.objects.count(), EmailOutbox.objects.count()), (2, 2))
