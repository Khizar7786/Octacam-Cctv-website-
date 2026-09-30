import re
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from apps.communications.email import PermanentEmailError, render_email
from apps.communications.models import EmailOutbox
from apps.communications.services import enqueue_email, process_one_email
from apps.orders.models import Order
from apps.orders.tracking import get_order_for_guest_token


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class OrderStatusEmailTests(TestCase):
    def make_order(self, *, user=None):
        return Order.objects.create(
            reference="OC-STATUS-1",
            user=user,
            customer_name="A Buyer",
            customer_email="buyer@example.com",
            customer_phone="03000000000",
            delivery_address_line1="Private street address",
            delivery_city="Lahore",
            delivery_province="Punjab",
            subtotal=Decimal("1000.00"),
            tax_total=Decimal("100.00"),
            shipping_fee=Decimal("200.00"),
            shipping_tax_amount=Decimal("0.00"),
            grand_total=Decimal("1300.00"),
            tax_rate_percent=Decimal("10.00"),
            shipping_taxable=False,
            idempotency_key=uuid.uuid4(),
            request_fingerprint="a" * 64,
        )

    def make_message(self, order, **changes):
        context = {
            "order_id": order.pk,
            "from_status": "packed",
            "to_status": "shipped",
            "courier_name": "Example courier",
            "tracking_number": "TRACK-1",
            "tracking_url": "https://courier.example/track/TRACK-1",
        }
        context.update(changes)
        return enqueue_email(
            event_type=EmailOutbox.EventType.ORDER_STATUS_CHANGED,
            recipient=order.customer_email,
            template_name="order_status_changed",
            context=context,
            dedupe_key=f"order-status:{order.pk}:{uuid.uuid4()}",
            order=order,
        )

    def test_delayed_guest_email_uses_event_snapshot_and_private_tracking_link(self):
        order = self.make_order()
        message = self.make_message(order)
        order.status = Order.Status.DELIVERED
        order.courier_name = "Later courier"
        order.tracking_number = "LATER-2"
        order.save(update_fields=["status", "courier_name", "tracking_number"])

        self.assertEqual(process_one_email(), "sent")
        message.refresh_from_db()
        self.assertEqual(message.status, EmailOutbox.Status.SENT)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, [order.customer_email])
        self.assertEqual(email.subject, f"OctaCam order {order.reference} status update")
        self.assertIn("moved from Packed to Shipped", email.body)
        self.assertIn("Example courier", email.body)
        self.assertIn("TRACK-1", email.body)
        self.assertNotIn("Later courier", email.body)
        self.assertNotIn("LATER-2", email.body)
        self.assertNotIn("Private street address", email.body)
        self.assertNotIn(order.customer_email, email.subject)
        link = re.search(r"/api/v1/orders/track/([^\s/]+)/", email.body)
        self.assertIsNotNone(link)
        self.assertEqual(get_order_for_guest_token(link.group(1)).pk, order.pk)

    def test_registered_customer_email_has_no_guest_link(self):
        user = get_user_model().objects.create_user(
            email="registered@example.com", password="test-password", full_name="Buyer",
        )
        order = self.make_order(user=user)
        message = self.make_message(order, courier_name="", tracking_number="", tracking_url="")
        _, body = render_email(message)
        self.assertIn("moved from Packed to Shipped", body)
        self.assertNotIn("/api/v1/orders/track/", body)
        self.assertNotIn("Courier details provided", body)

    def test_wrong_recipient_and_malformed_snapshot_fail_permanently(self):
        order = self.make_order()
        message = self.make_message(order)
        message.recipient = "other@example.com"
        with self.assertRaises(PermanentEmailError):
            render_email(message)

        message.recipient = order.customer_email
        for bad_context in (
            {"order_id": True, "from_status": "packed", "to_status": "shipped",
             "courier_name": "", "tracking_number": "", "tracking_url": ""},
            {"order_id": order.pk, "from_status": "packed", "to_status": "unknown",
             "courier_name": "", "tracking_number": "", "tracking_url": ""},
            {"order_id": order.pk, "from_status": "packed", "to_status": "shipped"},
        ):
            message.context = bad_context
            with self.subTest(bad_context=bad_context), self.assertRaises(PermanentEmailError):
                render_email(message)

    def test_mismatched_order_foreign_key_fails_permanently(self):
        order = self.make_order()
        message = self.make_message(order)
        message.order_id = order.pk + 1
        with self.assertRaises(PermanentEmailError):
            render_email(message)
        message.order_id = None
        with self.assertRaises(PermanentEmailError):
            render_email(message)
