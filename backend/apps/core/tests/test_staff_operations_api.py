from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from apps.communications.models import EmailOutbox
from apps.orders.models import Order
from apps.orders.tests.test_staff_order_api import make_order
from apps.surveys.models import SurveySlot
from apps.surveys.tests.test_slot_api import future_start, make_booking


OVERVIEW = "/api/v1/staff/overview/"
ACTIVITY = "/api/v1/staff/activity/"
UPCOMING = "/api/v1/staff/surveys/bookings/?upcoming=true"
FAILED_EMAILS = "/api/v1/staff/communications/emails/?status=failed"


class StaffOperationsApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(
            email="operations-staff@example.com", password="test-password", full_name="Staff", is_staff=True,
        )
        cls.customer = get_user_model().objects.create_user(
            email="operations-customer@example.com", password="test-password", full_name="Customer",
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.staff)

    def make_slot_booking(self, days, *, status="confirmed"):
        start = future_start(days)
        slot = SurveySlot.objects.create(starts_at=start, ends_at=start + timedelta(hours=1), capacity=1)
        return make_booking(slot, status=status)

    def make_email(self, index, *, status="failed"):
        return EmailOutbox.objects.create(
            event_type=EmailOutbox.EventType.ORDER_PLACED,
            recipient=f"private-{index}@example.com", template_name="order_placed",
            context={"secret": "private-email-context"}, dedupe_key=f"operations-{index}",
            status=status, next_attempt_at=None,
        )

    def test_staff_only_routes_and_private_headers(self):
        email = self.make_email(1)
        urls = [OVERVIEW, ACTIVITY, UPCOMING, FAILED_EMAILS]
        for user, expected in ((None, 401), (self.customer, 403)):
            self.client.force_authenticate(user=user)
            for url in urls:
                with self.subTest(user=user, url=url):
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, expected, response.data)
                    self.assertEqual(response["Cache-Control"], "private, no-store")
                    self.assertEqual(response["Referrer-Policy"], "no-referrer")
                    self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
            response = self.client.post(f"/api/v1/staff/communications/emails/{email.pk}/retry/")
            self.assertEqual(response.status_code, expected, response.data)
            self.assertEqual(response["Cache-Control"], "private, no-store")
        self.staff.is_active = False
        self.staff.save(update_fields=["is_active"])
        self.client.force_authenticate(user=self.staff)
        self.assertEqual(self.client.get(OVERVIEW).status_code, 403)
        email.refresh_from_db()
        self.assertEqual(email.status, "failed")

    def test_overview_counts_bounded_previews_and_minimal_audit_fields(self):
        statuses = ["placed", "confirmed", "packed", "shipped", "delivered", "cancelled", "placed"]
        orders = [make_order(reference=f"OCT-OPS-{index:03d}") for index in range(len(statuses))]
        for order, status in zip(orders, statuses):
            Order.objects.filter(pk=order.pk).update(status=status)
        bookings = [self.make_slot_booking(days) for days in range(7, 14)]
        cancelled = self.make_slot_booking(15, status="cancelled")
        completed = self.make_slot_booking(16, status="completed")
        past = self.make_slot_booking(-2)
        for booking in (*bookings, cancelled, completed, past):
            type(booking).objects.filter(pk=booking.pk).update(internal_notes="private-internal-note")
        events = [AuditEvent.objects.create(
            actor=self.staff, resource_type="Order", resource_id=str(order.pk), action="ORDER_UPDATED",
            before_data={"secret": "private-audit-payload"},
            after_data={"secret": "private-audit-payload"},
            metadata={"secret": "private-audit-payload"},
        ) for order in orders]
        failed = [self.make_email(index) for index in range(7)]
        self.make_email(7, status="pending")
        self.make_email(8, status="sent")

        response = self.client.get(OVERVIEW)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        data = response.data
        self.assertEqual(
            tuple(data[key] for key in (
                "placed_orders_count", "open_orders_count", "upcoming_surveys_count", "failed_emails_count",
            )), (2, 5, 7, 7),
        )
        self.assertEqual([row["reference"] for row in data["recent_orders"]],
                         [order.reference for order in reversed(orders[-5:])])
        self.assertEqual([row["reference"] for row in data["upcoming_surveys"]],
                         [booking.reference for booking in bookings[:5]])
        self.assertTrue(data["upcoming_surveys"][0]["scheduled_starts_at"].endswith("+05:00"))
        self.assertEqual([row["id"] for row in data["recent_activity"]],
                         [event.pk for event in reversed(events[-5:])])
        self.assertEqual([row["id"] for row in data["failed_emails"]],
                         [email.pk for email in reversed(failed[-5:])])
        self.assertEqual(data["recent_activity"][0]["actor_email"], self.staff.email)
        self.assertNotIn("private-audit-payload", str(data))
        self.assertNotIn("private-internal-note", str(data))
        self.assertNotIn("private-email-context", str(data))
        self.assertNotIn("before_data", str(data))
        self.assertNotIn("context", data["failed_emails"][0])

    def test_empty_overview_and_paginated_activity_upcoming_and_failed_emails(self):
        empty = self.client.get(OVERVIEW)
        self.assertEqual(empty.status_code, 200)
        for name in ("recent_orders", "upcoming_surveys", "recent_activity", "failed_emails"):
            self.assertEqual(empty.data[name], [])
        for name in ("placed_orders_count", "open_orders_count", "upcoming_surveys_count", "failed_emails_count"):
            self.assertEqual(empty.data[name], 0)

        events = [AuditEvent.objects.create(
            actor=self.staff, resource_type="SurveyBooking", resource_id=str(index), action="BOOKING_UPDATED",
            before_data={"private": "payload"},
        ) for index in range(25)]
        same_time = timezone.now()
        AuditEvent.objects.filter(pk__in=[event.pk for event in events]).update(created_at=same_time)
        orders = [make_order(reference=f"OCT-PAGE-{index:03d}") for index in range(25)]
        bookings = [self.make_slot_booking(days) for days in range(7, 32)]
        emails = [self.make_email(index) for index in range(25)]

        for url, expected_ids, key in (
            (ACTIVITY, [event.pk for event in reversed(events)], "id"),
            ("/api/v1/staff/orders/", [order.reference for order in reversed(orders)], "reference"),
            (UPCOMING, [booking.reference for booking in bookings], "reference"),
            (FAILED_EMAILS, [email.pk for email in reversed(emails)], "id"),
        ):
            with self.subTest(url=url):
                first = self.client.get(url)
                second = self.client.get(f"{url}&page=2" if "?" in url else f"{url}?page=2")
                self.assertEqual((first.status_code, second.status_code), (200, 200))
                self.assertEqual(first.data["count"], 25)
                self.assertEqual(len(first.data["results"]), 20)
                self.assertEqual(len(second.data["results"]), 5)
                self.assertEqual([row[key] for row in first.data["results"] + second.data["results"]], expected_ids)
                self.assertIsNone(second.data["next"])
                self.assertEqual(first["Cache-Control"], "private, no-store")
        self.assertNotIn("before_data", self.client.get(ACTIVITY).data["results"][0])
        self.assertEqual(self.client.get("/api/v1/staff/surveys/bookings/?upcoming=bogus").status_code, 400)
