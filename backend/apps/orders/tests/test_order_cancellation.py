from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.db import IntegrityError, close_old_connections, transaction
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from apps.catalog.models import InventoryMovement
from apps.communications.models import EmailOutbox
from apps.communications.services import process_one_email
from apps.orders.fulfillment_services import cancel_order
from apps.orders.models import Order
from apps.orders.tests.test_checkout_api import CHECKOUT_SETTINGS, make_product
from apps.orders.tests.test_staff_order_api import make_order


def make_stocked_order(*, reference):
    product = make_product(stock=0)
    order = make_order(reference=reference)
    item = order.items.get()
    item.product = product
    item.quantity = 2
    item.save(update_fields=["product", "quantity"])
    InventoryMovement.objects.create(
        product=product, order=order, quantity_delta=-2, previous_quantity=2,
        new_quantity=0, reason=InventoryMovement.Reason.ORDER_PLACED,
    )
    return order, product


@CHECKOUT_SETTINGS
class StaffCancellationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(
            email="cancel-staff@example.com", password="test-password", full_name="Staff", is_staff=True,
        )
        cls.customer = get_user_model().objects.create_user(
            email="cancel-customer@example.com", password="test-password", full_name="Customer",
        )

    def setUp(self):
        self.order, self.product = make_stocked_order(reference="OCT-CANCEL-001")
        self.url = f"/api/v1/staff/orders/{self.order.public_id}/cancel/"
        self.client = APIClient()

    def cancel(self, *, version=0, reason="Customer requested cancellation through support"):
        return self.client.post(self.url, {"expected_version": version, "reason": reason}, format="json")

    def test_staff_cancel_restocks_once_audits_and_emails_guest(self):
        self.client.force_authenticate(user=self.staff)
        response = self.cancel()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "cancelled")
        self.assertEqual(response.data["version"], 1)
        self.assertIsNotNone(response.data["cancelled_at"])
        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 2)
        self.assertIsNotNone(self.order.cancelled_at)
        movement = InventoryMovement.objects.get(reason=InventoryMovement.Reason.ORDER_CANCELLED)
        self.assertEqual((movement.order_id, movement.product_id, movement.quantity_delta,
                          movement.previous_quantity, movement.new_quantity, movement.actor_id),
                         (self.order.pk, self.product.pk, 2, 0, 2, self.staff.pk))
        audit = AuditEvent.objects.get(action="ORDER_CANCELLED")
        self.assertEqual(audit.actor_id, self.staff.pk)
        self.assertEqual(audit.before_data, {"status": "placed"})
        self.assertEqual(audit.after_data, {"status": "cancelled"})
        self.assertEqual(audit.metadata["reason"], "Customer requested cancellation through support")
        self.assertEqual(audit.metadata["inventory_movement_ids"], [movement.pk])
        email = EmailOutbox.objects.get()
        self.assertEqual(email.event_type, EmailOutbox.EventType.ORDER_CANCELLED)
        self.assertEqual(email.context, {"order_id": self.order.pk, "from_status": "placed"})
        self.assertEqual(process_one_email(), "sent")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.order.reference, mail.outbox[0].body)
        self.assertIn("cancelled", mail.outbox[0].body)
        self.assertIn("/api/v1/orders/track/", mail.outbox[0].body)
        self.assertNotIn(audit.metadata["reason"], mail.outbox[0].body)

        repeated = self.cancel(version=0)
        self.assertEqual(repeated.status_code, 200, repeated.data)
        self.assertEqual(repeated.data["version"], 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 2)
        self.assertEqual(InventoryMovement.objects.filter(reason="order_cancelled").count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action="ORDER_CANCELLED").count(), 1)
        self.assertEqual(EmailOutbox.objects.count(), 1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            InventoryMovement.objects.create(
                product=self.product, order=self.order, quantity_delta=2,
                previous_quantity=2, new_quantity=4,
                reason=InventoryMovement.Reason.ORDER_CANCELLED,
            )

    def test_confirmed_order_can_cancel_but_stale_active_version_cannot(self):
        self.client.force_authenticate(user=self.staff)
        self.order.status = Order.Status.CONFIRMED
        self.order.version = 1
        self.order.save(update_fields=["status", "version"])
        stale = self.cancel(version=0)
        self.assertEqual(stale.status_code, 409, stale.data)
        self.assertEqual(stale.data["error"]["code"], "ORDER_CHANGED")
        response = self.cancel(version=1)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["version"], 2)
        self.assertEqual(AuditEvent.objects.get(action="ORDER_CANCELLED").before_data, {"status": "confirmed"})

    def test_later_stages_and_collected_cod_are_rejected_without_restock(self):
        self.client.force_authenticate(user=self.staff)
        for stage, payment in (("packed", "uncollected"), ("shipped", "uncollected"),
                               ("delivered", "uncollected"), ("placed", "collected")):
            with self.subTest(stage=stage, payment=payment):
                Order.objects.filter(pk=self.order.pk).update(status=stage, payment_status=payment)
                response = self.cancel()
                self.assertEqual(response.status_code, 409, response.data)
                self.assertEqual(response.data["error"]["code"], "CANCELLATION_NOT_ALLOWED")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 0)
        self.assertFalse(InventoryMovement.objects.filter(reason="order_cancelled").exists())
        self.assertFalse(EmailOutbox.objects.exists())

    def test_permissions_and_reason_validation(self):
        for user, expected in ((None, 401), (self.customer, 403)):
            self.client.force_authenticate(user=user)
            self.assertEqual(self.cancel().status_code, expected)
        self.client.force_authenticate(user=self.staff)
        for body in ({"expected_version": 0}, {"expected_version": 0, "reason": "  "},
                     {"expected_version": 0, "reason": "Support", "restock": False}):
            with self.subTest(body=body):
                response = self.client.post(self.url, body, format="json")
                self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(self.product.stock_quantity, 0)
        self.assertFalse(EmailOutbox.objects.exists())

    def test_missing_product_and_overflow_fail_closed(self):
        self.client.force_authenticate(user=self.staff)
        item = self.order.items.get()
        item.product = None
        item.save(update_fields=["product"])
        response = self.cancel()
        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(response.data["error"]["code"], "RESTOCK_UNAVAILABLE")
        item.product = self.product
        item.save(update_fields=["product"])
        self.product.stock_quantity = 2_147_483_647
        self.product.save(update_fields=["stock_quantity"])
        response = self.cancel()
        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(response.data["error"]["code"], "RESTOCK_UNAVAILABLE")
        self.order.refresh_from_db()
        self.assertEqual((self.order.status, self.order.version), ("placed", 0))
        self.assertFalse(InventoryMovement.objects.filter(reason="order_cancelled").exists())

    def test_email_outbox_failure_rolls_back_order_stock_movement_and_audit(self):
        with patch("apps.orders.fulfillment_services.enqueue_email", side_effect=RuntimeError("outbox unavailable")):
            with self.assertRaises(RuntimeError):
                cancel_order(public_id=self.order.public_id, expected_version=0,
                             reason="Customer request", actor=self.staff)
        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual((self.order.status, self.order.version, self.product.stock_quantity), ("placed", 0, 0))
        self.assertIsNone(self.order.cancelled_at)
        self.assertFalse(InventoryMovement.objects.filter(reason="order_cancelled").exists())
        self.assertFalse(AuditEvent.objects.filter(action="ORDER_CANCELLED").exists())
        self.assertFalse(EmailOutbox.objects.exists())

    def test_email_delivery_failure_does_not_undo_cancellation(self):
        self.client.force_authenticate(user=self.staff)
        self.assertEqual(self.cancel().status_code, 200)
        with patch("apps.communications.services.deliver_email", side_effect=OSError("SMTP offline")):
            self.assertEqual(process_one_email(), "failed")
        self.order.refresh_from_db()
        self.product.refresh_from_db()
        event = EmailOutbox.objects.get()
        self.assertEqual((self.order.status, self.product.stock_quantity), ("cancelled", 2))
        self.assertEqual((event.status, event.attempt_count), (EmailOutbox.Status.FAILED, 1))
        self.assertEqual(InventoryMovement.objects.filter(reason="order_cancelled").count(), 1)

    def test_restock_requires_matching_placement_and_adds_to_current_stock(self):
        self.client.force_authenticate(user=self.staff)
        InventoryMovement.objects.filter(order=self.order, reason="order_placed").delete()
        response = self.cancel()
        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(response.data["error"]["code"], "RESTOCK_UNAVAILABLE")
        InventoryMovement.objects.create(
            product=self.product, order=self.order, quantity_delta=-2, previous_quantity=2,
            new_quantity=0, reason=InventoryMovement.Reason.ORDER_PLACED,
        )
        self.product.stock_quantity = 3
        self.product.save(update_fields=["stock_quantity"])
        response = self.cancel()
        self.assertEqual(response.status_code, 200, response.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 5)
        movement = InventoryMovement.objects.get(reason="order_cancelled")
        self.assertEqual((movement.previous_quantity, movement.new_quantity), (3, 5))


@CHECKOUT_SETTINGS
class StaffCancellationConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            email="cancel-race@example.com", password="test-password", full_name="Staff", is_staff=True,
        )
        self.order, self.product = make_stocked_order(reference="OCT-CANCEL-RACE")
        self.url = f"/api/v1/staff/orders/{self.order.public_id}/cancel/"

    def test_concurrent_cancellation_restocks_once(self):
        first_cancelled = Event()
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
                    response = client().post(self.url, {"expected_version": 0, "reason": "Support request"}, format="json")
                    first_cancelled.set()
                    if not release_first.wait(10):
                        raise AssertionError("Timed out releasing first cancellation")
                    return response.status_code
            finally:
                close_old_connections()

        def second():
            close_old_connections()
            try:
                second_started.set()
                response = client().post(self.url, {"expected_version": 0, "reason": "Support request"}, format="json")
                return response.status_code, response.data
            finally:
                second_done.set()
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            first_future = pool.submit(first)
            try:
                self.assertTrue(first_cancelled.wait(10))
                second_future = pool.submit(second)
                self.assertTrue(second_started.wait(10))
                self.assertFalse(second_done.wait(0.2), "The second cancellation bypassed the order lock")
            finally:
                release_first.set()
            self.assertEqual(first_future.result(timeout=10), 200)
            second_status, second_data = second_future.result(timeout=10)

        self.assertEqual(second_status, 200, second_data)
        self.assertEqual(second_data["version"], 1)
        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual((self.order.status, self.order.version, self.product.stock_quantity), ("cancelled", 1, 2))
        self.assertEqual(InventoryMovement.objects.filter(reason="order_cancelled").count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action="ORDER_CANCELLED").count(), 1)
        self.assertEqual(EmailOutbox.objects.filter(event_type="ORDER_CANCELLED").count(), 1)
