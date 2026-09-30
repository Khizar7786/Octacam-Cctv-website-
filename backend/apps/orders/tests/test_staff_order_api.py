import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Event
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.db import close_old_connections, transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from apps.communications.models import EmailOutbox
from apps.communications.services import process_email_batch, process_one_email
from apps.orders.fulfillment_services import transition_order
from apps.orders.models import Order, OrderItem
from apps.orders.tests.test_checkout_api import CHECKOUT_SETTINGS


def make_order(*, reference="OCT-STAFF-001", customer_email="guest@example.com"):
    order = Order.objects.create(
        reference=reference,
        customer_name="Guest Buyer",
        customer_email=customer_email,
        customer_phone="03001234567",
        delivery_address_line1="12 Camera Street",
        delivery_address_line2="Floor 2",
        delivery_city="Lahore",
        delivery_province="Punjab",
        delivery_postal_code="54000",
        delivery_country="PK",
        subtotal=Decimal("900.00"),
        tax_total=Decimal("90.00"),
        shipping_fee=Decimal("250.00"),
        shipping_tax_amount=Decimal("0.00"),
        grand_total=Decimal("1240.00"),
        tax_rate_percent=Decimal("10.00"),
        shipping_taxable=False,
        idempotency_key=uuid.uuid4(),
        request_fingerprint="a" * 64,
    )
    OrderItem.objects.create(
        order=order, product_name="Camera at checkout", sku="CAM-1", quantity=1,
        unit_price=Decimal("900.00"), line_subtotal=Decimal("900.00"), tax_amount=Decimal("90.00"),
    )
    return order


@CHECKOUT_SETTINGS
class StaffOrderApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(
            email="staff@example.com", password="test-password", full_name="Staff", is_staff=True,
        )
        cls.customer = get_user_model().objects.create_user(
            email="customer@example.com", password="test-password", full_name="Customer",
        )

    def setUp(self):
        self.client = APIClient()
        self.order = make_order()
        self.detail_url = f"/api/v1/staff/orders/{self.order.public_id}/"
        self.transition_url = f"{self.detail_url}transition/"
        self.courier_url = f"{self.detail_url}courier/"
        self.cod_url = f"{self.detail_url}mark-cod-collected/"
        self.history_url = f"{self.detail_url}history/"

    def as_staff(self):
        self.client.force_authenticate(user=self.staff)

    def transition(self, status, version):
        return self.client.post(
            self.transition_url, {"status": status, "expected_version": version}, format="json",
        )

    def test_staff_only_list_detail_history_and_commands(self):
        requests = [
            ("get", "/api/v1/staff/orders/", None),
            ("get", self.detail_url, None),
            ("get", self.history_url, None),
            ("post", self.transition_url, {"status": "confirmed", "expected_version": 0}),
            ("patch", self.courier_url, {"courier_name": "Courier", "expected_version": 0}),
            ("post", self.cod_url, {"expected_version": 0}),
        ]
        for user, expected_status in ((None, 401), (self.customer, 403)):
            self.client.force_authenticate(user=user)
            for method, url, body in requests:
                with self.subTest(user=user, method=method, url=url):
                    response = getattr(self.client, method)(url, body, format="json") if body is not None else self.client.get(url)
                    self.assertEqual(response.status_code, expected_status, response.data)
        self.order.refresh_from_db()
        self.assertEqual((self.order.status, self.order.payment_status, self.order.version),
                         (Order.Status.PLACED, Order.PaymentStatus.UNCOLLECTED, 0))
        self.assertFalse(AuditEvent.objects.exists())
        self.assertFalse(EmailOutbox.objects.exists())

        self.as_staff()
        for url in ("/api/v1/staff/orders/", self.detail_url, self.history_url):
            self.assertEqual(self.client.get(url).status_code, 200)

    def test_list_filters_reference_status_and_payment_state(self):
        second = make_order(reference="OCT-STAFF-002", customer_email="second@example.com")
        Order.objects.filter(pk=second.pk).update(status=Order.Status.SHIPPED, payment_status=Order.PaymentStatus.COLLECTED)
        self.as_staff()

        all_orders = self.client.get("/api/v1/staff/orders/")
        self.assertEqual(all_orders.status_code, 200, all_orders.data)
        self.assertEqual(all_orders.data["count"], 2)
        self.assertEqual({row["reference"] for row in all_orders.data["results"]},
                         {self.order.reference, second.reference})
        self.assertTrue(all("version" in row for row in all_orders.data["results"]))

        for query, expected in (
            ("status=shipped", second.reference),
            ("payment_status=collected", second.reference),
            ("q=STAFF-002", second.reference),
            ("q=STAFF-001", self.order.reference),
        ):
            response = self.client.get(f"/api/v1/staff/orders/?{query}")
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data["count"], 1)
            self.assertEqual(response.data["results"][0]["reference"], expected)

    def test_staff_detail_uses_saved_snapshots_and_excludes_private_operational_tokens(self):
        self.as_staff()
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["version"], 0)
        self.assertEqual(response.data["customer_email"], "guest@example.com")
        self.assertEqual(response.data["customer_phone"], "03001234567")
        self.assertEqual(response.data["delivery_address_line1"], "12 Camera Street")
        self.assertEqual(response.data["grand_total"], "1240.00")
        self.assertEqual(response.data["items"][0]["product_name"], "Camera at checkout")
        self.assertNotIn("idempotency_key", response.data)
        self.assertNotIn("request_fingerprint", response.data)
        self.assertNotIn("guest_link_nonce", response.data)
        self.assertNotIn("guest_tracking_url", response.data)

    def test_order_follows_each_stage_with_audit_and_one_email_event_per_change(self):
        self.as_staff()
        for version, new_status in enumerate(("confirmed", "packed", "shipped", "delivered")):
            response = self.transition(new_status, version)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data["status"], new_status)
            self.assertEqual(response.data["version"], version + 1)
            self.order.refresh_from_db()
            self.assertEqual(self.order.status, new_status)
            self.assertEqual(self.order.payment_status, Order.PaymentStatus.UNCOLLECTED)
            self.assertEqual(AuditEvent.objects.filter(action="ORDER_STATUS_CHANGED").count(), version + 1)
            self.assertEqual(EmailOutbox.objects.filter(event_type="ORDER_STATUS_CHANGED").count(), version + 1)
        events = AuditEvent.objects.filter(action="ORDER_STATUS_CHANGED").order_by("id")
        self.assertTrue(all(event.actor_id == self.staff.pk for event in events))
        self.assertEqual([event.after_data["status"] for event in events],
                         ["confirmed", "packed", "shipped", "delivered"])

        history = self.client.get(self.history_url)
        self.assertEqual(history.status_code, 200, history.data)
        self.assertEqual(history.data["count"], 4)
        self.assertEqual(history.data["results"][0]["action"], "ORDER_STATUS_CHANGED")
        self.assertEqual(history.data["results"][0]["actor_email"], self.staff.email)
        self.assertEqual(history.data["results"][0]["after_data"]["status"], "delivered")

    def test_invalid_repeated_and_cancelled_transitions_do_not_write(self):
        self.as_staff()
        for status in ("shipped", "cancelled"):
            response = self.transition(status, 0)
            self.assertEqual(response.status_code, 409, response.data)
            self.assertEqual(response.data["error"]["code"], "INVALID_STATUS_TRANSITION")
        self.assertEqual(self.client.patch(self.detail_url, {"status": "shipped"}, format="json").status_code, 405)

        confirmed = self.transition("confirmed", 0)
        self.assertEqual(confirmed.status_code, 200, confirmed.data)
        repeated = self.transition("confirmed", 1)
        self.assertEqual(repeated.status_code, 409, repeated.data)
        self.assertEqual(repeated.data["error"]["code"], "INVALID_STATUS_TRANSITION")
        self.order.refresh_from_db()
        self.assertEqual((self.order.status, self.order.version), ("confirmed", 1))
        self.assertEqual(AuditEvent.objects.filter(action="ORDER_STATUS_CHANGED").count(), 1)
        self.assertEqual(EmailOutbox.objects.filter(event_type="ORDER_STATUS_CHANGED").count(), 1)

    def test_stale_stage_request_conflicts_without_overwriting_newer_state(self):
        self.as_staff()
        self.assertEqual(self.transition("confirmed", 0).status_code, 200)
        stale = self.transition("packed", 0)
        self.assertEqual(stale.status_code, 409, stale.data)
        self.assertEqual(stale.data["error"]["code"], "ORDER_CHANGED")
        self.order.refresh_from_db()
        self.assertEqual((self.order.status, self.order.version), ("confirmed", 1))
        self.assertEqual(EmailOutbox.objects.count(), 1)

    def test_courier_updates_are_partial_idempotent_audited_and_versioned(self):
        self.as_staff()
        first = self.client.patch(self.courier_url, {
            "expected_version": 0, "courier_name": "Local Courier", "tracking_number": "TRK-123",
            "tracking_url": "https://courier.example/track/TRK-123",
        }, format="json")
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(first.data["version"], 1)
        self.assertEqual(first.data["status"], "placed")
        self.assertEqual(first.data["tracking_number"], "TRK-123")
        self.assertEqual(AuditEvent.objects.filter(action="COURIER_UPDATED").count(), 1)
        self.assertFalse(EmailOutbox.objects.exists())

        repeated = self.client.patch(self.courier_url, {
            "expected_version": 1, "courier_name": "Local Courier", "tracking_number": "TRK-123",
            "tracking_url": "https://courier.example/track/TRK-123",
        }, format="json")
        self.assertEqual(repeated.status_code, 200, repeated.data)
        self.assertEqual(repeated.data["version"], 1)
        self.assertEqual(AuditEvent.objects.filter(action="COURIER_UPDATED").count(), 1)

        stale = self.client.patch(self.courier_url, {
            "expected_version": 0, "tracking_number": "OVERWRITE",
        }, format="json")
        self.assertEqual(stale.status_code, 409, stale.data)
        self.assertEqual(stale.data["error"]["code"], "ORDER_CHANGED")
        self.order.refresh_from_db()
        self.assertEqual(self.order.tracking_number, "TRK-123")

        updated = self.client.patch(self.courier_url, {
            "expected_version": 1, "tracking_number": "TRK-456",
        }, format="json")
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(updated.data["version"], 2)
        self.assertEqual(updated.data["courier_name"], "Local Courier")
        self.assertEqual(AuditEvent.objects.filter(action="COURIER_UPDATED").count(), 2)

    def test_cod_collection_is_independent_and_repeated_action_is_a_no_op(self):
        self.as_staff()
        collected = self.client.post(self.cod_url, {"expected_version": 0}, format="json")
        self.assertEqual(collected.status_code, 200, collected.data)
        self.assertEqual(collected.data["payment_status"], "collected")
        self.assertEqual(collected.data["status"], "placed")
        self.assertEqual(collected.data["version"], 1)
        repeated = self.client.post(self.cod_url, {"expected_version": 1}, format="json")
        self.assertEqual(repeated.status_code, 200, repeated.data)
        self.assertEqual(repeated.data["version"], 1)
        self.assertEqual(AuditEvent.objects.filter(action="COD_MARKED_COLLECTED").count(), 1)
        self.assertFalse(EmailOutbox.objects.exists())

    def test_failed_status_email_retries_without_rolling_back_order(self):
        self.as_staff()
        changed = self.transition("confirmed", 0)
        self.assertEqual(changed.status_code, 200, changed.data)
        with patch("apps.communications.services.deliver_email", side_effect=OSError("SMTP offline")):
            self.assertEqual(process_one_email(), "failed")
        self.order.refresh_from_db()
        event = EmailOutbox.objects.get()
        self.assertEqual(self.order.status, "confirmed")
        self.assertEqual(event.status, EmailOutbox.Status.FAILED)
        self.assertEqual(event.attempt_count, 1)

        EmailOutbox.objects.filter(pk=event.pk).update(next_attempt_at=timezone.now())
        self.assertEqual(process_one_email(), "sent")
        event.refresh_from_db()
        self.assertEqual(event.status, EmailOutbox.Status.SENT)
        self.assertEqual(event.attempt_count, 2)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.order.reference, mail.outbox[0].body)
        self.assertIn("confirmed", mail.outbox[0].body.lower())

    def test_status_and_audit_roll_back_if_outbox_write_fails(self):
        with patch("apps.orders.fulfillment_services.enqueue_email", side_effect=RuntimeError("outbox unavailable")):
            with self.assertRaises(RuntimeError):
                transition_order(
                    public_id=self.order.public_id, status="confirmed", expected_version=0, actor=self.staff,
                )
        self.order.refresh_from_db()
        self.assertEqual((self.order.status, self.order.version), ("placed", 0))
        self.assertFalse(AuditEvent.objects.exists())
        self.assertFalse(EmailOutbox.objects.exists())

    def test_delayed_email_uses_each_queued_stage_snapshot(self):
        self.as_staff()
        self.assertEqual(self.transition("confirmed", 0).status_code, 200)
        self.assertEqual(self.transition("packed", 1).status_code, 200)
        self.assertEqual(process_email_batch(), ["sent", "sent"])
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("confirmed", mail.outbox[0].body.lower())
        self.assertIn("packed", mail.outbox[1].body.lower())
        self.assertEqual(EmailOutbox.objects.filter(event_type="ORDER_STATUS_CHANGED").count(), 2)


@CHECKOUT_SETTINGS
class StaffOrderConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            email="staff-race@example.com", password="test-password", full_name="Staff", is_staff=True,
        )
        self.order = make_order(reference="OCT-RACE-001")
        self.base_url = f"/api/v1/staff/orders/{self.order.public_id}/"

    def test_concurrent_stage_and_courier_edits_cannot_both_accept_old_version(self):
        first_changed = Event()
        release_first = Event()
        second_started = Event()
        second_done = Event()

        def client():
            api = APIClient()
            api.force_authenticate(user=self.staff)
            return api

        def first():
            close_old_connections()
            try:
                with transaction.atomic():
                    response = client().post(
                        f"{self.base_url}transition/", {"status": "confirmed", "expected_version": 0}, format="json",
                    )
                    first_changed.set()
                    if not release_first.wait(10):
                        raise AssertionError("Timed out releasing first order update")
                    return response.status_code
            finally:
                close_old_connections()

        def second():
            close_old_connections()
            try:
                second_started.set()
                response = client().patch(
                    f"{self.base_url}courier/", {"courier_name": "Race Courier", "expected_version": 0},
                    format="json",
                )
                return response.status_code, response.data
            finally:
                second_done.set()
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            first_future = pool.submit(first)
            try:
                self.assertTrue(first_changed.wait(10))
                second_future = pool.submit(second)
                self.assertTrue(second_started.wait(10))
                self.assertFalse(second_done.wait(0.2), "The second update bypassed the order row lock")
            finally:
                release_first.set()
            first_status = first_future.result(timeout=10)
            second_status, second_data = second_future.result(timeout=10)

        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 409, second_data)
        self.assertEqual(second_data["error"]["code"], "ORDER_CHANGED")
        self.order.refresh_from_db()
        self.assertEqual((self.order.status, self.order.courier_name, self.order.version), ("confirmed", "", 1))
        self.assertEqual(AuditEvent.objects.filter(action="ORDER_STATUS_CHANGED").count(), 1)
        self.assertFalse(AuditEvent.objects.filter(action="COURIER_UPDATED").exists())
        self.assertEqual(EmailOutbox.objects.filter(event_type="ORDER_STATUS_CHANGED").count(), 1)
