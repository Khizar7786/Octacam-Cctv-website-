import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone as utc_timezone
from threading import Event
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.db import close_old_connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from apps.surveys.models import SurveyBooking, SurveySlot


STAFF_SLOTS = "/api/v1/staff/surveys/slots/"
PUBLIC_SLOTS = "/api/v1/surveys/slots/"
KARACHI = ZoneInfo("Asia/Karachi")


def future_start(days=7):
    return (timezone.localtime(timezone.now(), KARACHI) + timedelta(days=days)).replace(
        hour=10, minute=0, second=0, microsecond=0,
    )


def make_booking(slot, *, status="confirmed", reference=None):
    return SurveyBooking.objects.create(
        slot=slot,
        reference=reference or f"OCT-SURVEY-{uuid.uuid4().hex[:12].upper()}",
        customer_name="Lahore customer",
        customer_email="survey-customer@example.com",
        customer_phone="03001234567",
        site_address_line1="12 Camera Street",
        site_city="Lahore",
        needs_description="Survey the existing cameras.",
        status=status,
        idempotency_key=uuid.uuid4(),
        request_fingerprint="a" * 64,
    )


@override_settings(SURVEY_SLOT_DURATION_MINUTES="60")
class SurveySlotApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(
            email="slot-staff@example.com", password="test-password", full_name="Staff", is_staff=True,
        )
        cls.customer = get_user_model().objects.create_user(
            email="slot-customer@example.com", password="test-password", full_name="Customer",
        )

    def setUp(self):
        self.client = APIClient()

    def as_staff(self):
        self.client.force_authenticate(user=self.staff)

    def create_slot(self, *, days=7, capacity=2, is_open=True):
        response = self.client.post(STAFF_SLOTS, {
            "starts_at": future_start(days).isoformat(), "capacity": capacity, "is_open": is_open,
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return SurveySlot.objects.get(public_id=response.data["public_id"])

    def test_staff_routes_require_staff_but_public_availability_is_open(self):
        self.as_staff()
        slot = self.create_slot()
        detail = f"{STAFF_SLOTS}{slot.public_id}/"
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(PUBLIC_SLOTS).status_code, 200)
        for user, expected in ((None, 401), (self.customer, 403)):
            self.client.force_authenticate(user=user)
            for method, url, body in (
                ("get", STAFF_SLOTS, None),
                ("post", STAFF_SLOTS, {"starts_at": future_start(8).isoformat(), "capacity": 1}),
                ("get", detail, None),
                ("patch", detail, {"expected_version": 0, "capacity": 1}),
            ):
                with self.subTest(user=user, method=method, url=url):
                    response = getattr(self.client, method)(url, body, format="json") if body else self.client.get(url)
                    self.assertEqual(response.status_code, expected, response.data)
        slot.refresh_from_db()
        self.assertEqual((slot.capacity, slot.version), (2, 0))
        self.assertEqual(SurveySlot.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(resource_type="SurveySlot").count(), 1)
        self.assertEqual(self.client.post(PUBLIC_SLOTS, {}, format="json").status_code, 405)

    def test_create_computes_end_from_configuration_and_serializes_karachi_time(self):
        self.as_staff()
        local_start = future_start()
        utc_start = local_start.astimezone(utc_timezone.utc)
        response = self.client.post(STAFF_SLOTS, {
            "starts_at": utc_start.isoformat(), "capacity": 3,
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        slot = SurveySlot.objects.get(public_id=response.data["public_id"])
        self.assertEqual(slot.starts_at, utc_start)
        self.assertEqual(slot.ends_at - slot.starts_at, timedelta(minutes=60))
        self.assertEqual((slot.capacity, slot.is_open, slot.version), (3, True, 0))
        self.assertEqual((response.data["booked_count"], response.data["remaining_capacity"]), (0, 3))
        self.assertEqual(datetime.fromisoformat(response.data["starts_at"]), local_start)
        self.assertEqual(datetime.fromisoformat(response.data["ends_at"]), local_start + timedelta(hours=1))
        self.assertTrue(response.data["starts_at"].endswith("+05:00"))
        self.assertEqual(slot.created_by_id, self.staff.pk)
        audit = AuditEvent.objects.get(action="SURVEY_SLOT_CREATED")
        self.assertEqual((audit.actor_id, audit.resource_type, audit.resource_id),
                         (self.staff.pk, "SurveySlot", str(slot.pk)))

        public = self.client.get(PUBLIC_SLOTS)
        self.assertEqual(public.status_code, 200, public.data)
        self.assertEqual(public.data["count"], 1)
        self.assertEqual(set(public.data["results"][0]), {"public_id", "starts_at", "ends_at"})
        self.assertEqual(public.data["results"][0]["public_id"], str(slot.public_id))
        self.assertEqual(public.data["results"][0]["starts_at"], response.data["starts_at"])

    def test_invalid_time_capacity_and_client_end_are_rejected(self):
        self.as_staff()
        for body, field in (
            ({"starts_at": future_start().replace(tzinfo=None).isoformat(), "capacity": 1}, "starts_at"),
            ({"starts_at": "not a date", "capacity": 1}, "starts_at"),
            ({"starts_at": (timezone.now() - timedelta(minutes=1)).isoformat(), "capacity": 1}, "starts_at"),
            ({"starts_at": future_start().isoformat(), "capacity": 0}, "capacity"),
            ({"starts_at": future_start().isoformat(), "capacity": -1}, "capacity"),
            ({"starts_at": future_start().isoformat(), "capacity": 1,
              "ends_at": (future_start() + timedelta(hours=2)).isoformat()}, "ends_at"),
        ):
            with self.subTest(body=body):
                response = self.client.post(STAFF_SLOTS, body, format="json")
                self.assertEqual(response.status_code, 400, response.data)
                self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
                self.assertIn(field, response.data["error"]["fields"])
        self.assertFalse(SurveySlot.objects.exists())
        self.assertFalse(AuditEvent.objects.exists())

    def test_duplicate_start_is_rejected_without_extra_audit(self):
        self.as_staff()
        slot = self.create_slot()
        duplicate = self.client.post(STAFF_SLOTS, {
            "starts_at": future_start().astimezone(utc_timezone.utc).isoformat(), "capacity": 1,
        }, format="json")
        self.assertEqual(duplicate.status_code, 409, duplicate.data)
        self.assertEqual(duplicate.data["error"]["code"], "SLOT_TIME_TAKEN")
        slot.refresh_from_db()
        self.assertEqual(slot.version, 0)
        self.assertEqual(SurveySlot.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(resource_type="SurveySlot").count(), 1)

    def test_missing_duration_blocks_create_and_time_edit_but_not_capacity_edit(self):
        self.as_staff()
        slot = self.create_slot()
        detail = f"{STAFF_SLOTS}{slot.public_id}/"
        with override_settings(SURVEY_SLOT_DURATION_MINUTES=None):
            unavailable = self.client.post(STAFF_SLOTS, {
                "starts_at": future_start(8).isoformat(), "capacity": 1,
            }, format="json")
            self.assertEqual(unavailable.status_code, 503, unavailable.data)
            self.assertEqual(unavailable.data["error"]["code"], "SURVEY_NOT_CONFIGURED")
            reschedule = self.client.patch(detail, {
                "expected_version": 0, "starts_at": future_start(8).isoformat(),
            }, format="json")
            self.assertEqual(reschedule.status_code, 503, reschedule.data)
            self.assertEqual(reschedule.data["error"]["code"], "SURVEY_NOT_CONFIGURED")
            capacity = self.client.patch(detail, {"expected_version": 0, "capacity": 3}, format="json")
            self.assertEqual(capacity.status_code, 200, capacity.data)
            self.assertEqual(capacity.data["capacity"], 3)
        slot.refresh_from_db()
        self.assertEqual((slot.capacity, slot.version), (3, 1))
        self.assertEqual(SurveySlot.objects.count(), 1)

    def test_zero_or_nonnumeric_duration_blocks_creation(self):
        self.as_staff()
        for duration in ("0", "not-a-number"):
            with self.subTest(duration=duration), override_settings(SURVEY_SLOT_DURATION_MINUTES=duration):
                response = self.client.post(STAFF_SLOTS, {
                    "starts_at": future_start().isoformat(), "capacity": 1,
                }, format="json")
                self.assertEqual(response.status_code, 503, response.data)
                self.assertEqual(response.data["error"]["code"], "SURVEY_NOT_CONFIGURED")
        self.assertFalse(SurveySlot.objects.exists())
        self.assertFalse(AuditEvent.objects.exists())

    def test_availability_uses_non_cancelled_bookings_and_hides_closed_full_past_slots(self):
        self.as_staff()
        available = self.create_slot(days=7, capacity=3)
        full = self.create_slot(days=8, capacity=1)
        closed = self.create_slot(days=9, capacity=2, is_open=False)
        past = self.create_slot(days=10, capacity=1)
        SurveySlot.objects.filter(pk=past.pk).update(
            starts_at=timezone.now() - timedelta(days=1),
            ends_at=timezone.now() - timedelta(days=1) + timedelta(hours=1),
        )
        make_booking(available)
        make_booking(available, status="completed")
        make_booking(available, status="cancelled")
        make_booking(full)

        public = self.client.get(PUBLIC_SLOTS)
        self.assertEqual(public.status_code, 200, public.data)
        self.assertEqual([row["public_id"] for row in public.data["results"]], [str(available.public_id)])
        self.assertEqual(set(public.data["results"][0]), {"public_id", "starts_at", "ends_at"})
        staff = self.client.get(STAFF_SLOTS)
        self.assertEqual(staff.status_code, 200, staff.data)
        self.assertEqual(staff.data["count"], 4)
        rows = {row["public_id"]: row for row in staff.data["results"]}
        self.assertEqual((rows[str(available.public_id)]["booked_count"],
                          rows[str(available.public_id)]["remaining_capacity"]), (2, 1))
        self.assertEqual((rows[str(full.public_id)]["booked_count"],
                          rows[str(full.public_id)]["remaining_capacity"]), (1, 0))
        self.assertFalse(rows[str(closed.public_id)]["is_open"])
        self.assertIn(str(past.public_id), rows)

    def test_booked_slot_rejects_time_move_or_capacity_below_occupancy(self):
        self.as_staff()
        slot = self.create_slot(capacity=2)
        booking = make_booking(slot)
        detail = f"{STAFF_SLOTS}{slot.public_id}/"
        moved = self.client.patch(detail, {
            "expected_version": 0, "starts_at": future_start(8).isoformat(),
        }, format="json")
        self.assertEqual(moved.status_code, 409, moved.data)
        self.assertEqual(moved.data["error"]["code"], "SLOT_HAS_BOOKINGS")
        make_booking(slot)
        reduced = self.client.patch(detail, {"expected_version": 0, "capacity": 1}, format="json")
        self.assertEqual(reduced.status_code, 409, reduced.data)
        self.assertEqual(reduced.data["error"]["code"], "SLOT_CAPACITY_TOO_LOW")
        slot.refresh_from_db()
        booking.refresh_from_db()
        self.assertEqual((slot.capacity, slot.version, booking.slot_id), (2, 0, slot.pk))
        self.assertEqual(AuditEvent.objects.filter(action="SURVEY_SLOT_CHANGED").count(), 0)

    def test_close_preserves_booking_and_stale_version_cannot_overwrite(self):
        self.as_staff()
        slot = self.create_slot()
        booking = make_booking(slot)
        detail = f"{STAFF_SLOTS}{slot.public_id}/"
        closed = self.client.patch(detail, {"expected_version": 0, "is_open": False}, format="json")
        self.assertEqual(closed.status_code, 200, closed.data)
        self.assertEqual((closed.data["version"], closed.data["booked_count"]), (1, 1))
        self.assertFalse(closed.data["is_open"])
        self.assertEqual(self.client.get(PUBLIC_SLOTS).data["count"], 0)
        stale = self.client.patch(detail, {"expected_version": 0, "capacity": 3}, format="json")
        self.assertEqual(stale.status_code, 409, stale.data)
        self.assertEqual(stale.data["error"]["code"], "SLOT_CHANGED")
        stale_noop = self.client.patch(detail, {"expected_version": 0, "is_open": False}, format="json")
        self.assertEqual(stale_noop.status_code, 409, stale_noop.data)
        self.assertEqual(stale_noop.data["error"]["code"], "SLOT_CHANGED")
        slot.refresh_from_db()
        booking.refresh_from_db()
        self.assertEqual((slot.version, slot.capacity, booking.status, booking.slot_id),
                         (1, 2, "confirmed", slot.pk))
        audit = AuditEvent.objects.get(action="SURVEY_SLOT_CHANGED")
        self.assertEqual(audit.actor_id, self.staff.pk)
        self.assertEqual(audit.before_data["is_open"], True)
        self.assertEqual(audit.after_data["is_open"], False)

    def test_unbooked_slot_can_move_and_end_is_recalculated(self):
        self.as_staff()
        slot = self.create_slot()
        detail = f"{STAFF_SLOTS}{slot.public_id}/"
        for invalid_start in (
            future_start(8).replace(tzinfo=None).isoformat(),
            (timezone.now() - timedelta(minutes=1)).isoformat(),
        ):
            invalid = self.client.patch(detail, {
                "expected_version": 0, "starts_at": invalid_start,
            }, format="json")
            self.assertEqual(invalid.status_code, 400, invalid.data)
            self.assertIn("starts_at", invalid.data["error"]["fields"])
        slot.refresh_from_db()
        self.assertEqual(slot.version, 0)
        moved = self.client.patch(detail, {
            "expected_version": 0, "starts_at": future_start(8).isoformat(),
        }, format="json")
        self.assertEqual(moved.status_code, 200, moved.data)
        self.assertEqual(moved.data["version"], 1)
        slot.refresh_from_db()
        self.assertEqual(slot.starts_at, future_start(8))
        self.assertEqual(slot.ends_at - slot.starts_at, timedelta(minutes=60))


@override_settings(SURVEY_SLOT_DURATION_MINUTES="60")
class SurveySlotCapacityRaceTests(TransactionTestCase):
    def test_staff_capacity_edit_waits_for_bookings_then_rechecks_occupancy(self):
        staff = get_user_model().objects.create_user(
            email="slot-race-staff@example.com", password="test-password", full_name="Staff", is_staff=True,
        )
        slot = SurveySlot.objects.create(
            starts_at=future_start(), ends_at=future_start() + timedelta(hours=1),
            capacity=2, is_open=True, created_by=staff,
        )
        detail = f"{STAFF_SLOTS}{slot.public_id}/"
        bookings_written = Event()
        release_booking = Event()
        edit_started = Event()
        edit_done = Event()

        def booking_transaction():
            close_old_connections()
            try:
                with transaction.atomic():
                    locked = SurveySlot.objects.select_for_update().get(pk=slot.pk)
                    make_booking(locked)
                    make_booking(locked)
                    bookings_written.set()
                    if not release_booking.wait(10):
                        raise AssertionError("Timed out releasing booking transaction")
            finally:
                close_old_connections()

        def staff_edit():
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(user=staff)
                edit_started.set()
                response = client.patch(detail, {"expected_version": 0, "capacity": 1}, format="json")
                return response.status_code, response.data
            finally:
                edit_done.set()
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            booking_future = pool.submit(booking_transaction)
            try:
                self.assertTrue(bookings_written.wait(10))
                edit_future = pool.submit(staff_edit)
                self.assertTrue(edit_started.wait(10))
                self.assertFalse(edit_done.wait(0.2), "Capacity edit bypassed the slot lock")
            finally:
                release_booking.set()
            booking_future.result(timeout=10)
            status, data = edit_future.result(timeout=10)

        self.assertEqual(status, 409, data)
        self.assertEqual(data["error"]["code"], "SLOT_CAPACITY_TOO_LOW")
        slot.refresh_from_db()
        self.assertEqual((slot.capacity, slot.version, slot.bookings.count()), (2, 0, 2))
