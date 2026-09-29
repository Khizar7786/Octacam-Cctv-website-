import re
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.http import Http404
from django.test import TestCase, override_settings

from apps.communications.email import PermanentEmailError, render_email
from apps.communications.models import EmailOutbox
from apps.communications.services import process_one_email
from apps.orders.models import Order, OrderItem
from apps.orders.tracking import get_order_for_guest_token, make_guest_tracking_token


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class OrderEmailTests(TestCase):
    def make_order(self, *, user=None):
        order = Order.objects.create(
            reference="OC-TEST-1",
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
        OrderItem.objects.create(
            order=order,
            product_name="Camera & lens",
            sku="CAM-1",
            quantity=2,
            unit_price=Decimal("500.00"),
            line_subtotal=Decimal("1000.00"),
            tax_amount=Decimal("100.00"),
        )
        return order

    def make_message(self, order):
        return EmailOutbox.objects.create(
            event_type=EmailOutbox.EventType.ORDER_PLACED,
            recipient=order.customer_email,
            template_name="order_placed",
            context={"order_id": order.pk},
            dedupe_key=f"order-placed:{order.pk}",
        )

    def test_guest_email_uses_saved_amounts_and_private_tracking_link(self):
        order = self.make_order()
        message = self.make_message(order)
        self.assertEqual(process_one_email(), "sent")
        message.refresh_from_db()
        self.assertEqual(message.status, EmailOutbox.Status.SENT)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, [order.customer_email])
        self.assertIn(order.reference, email.subject)
        self.assertIn("Camera & lens", email.body)
        self.assertIn("PKR 1,300.00", email.body)
        self.assertNotIn("Private street address", email.body)
        link = re.search(r"/api/v1/orders/track/([^\s/]+)/", email.body)
        self.assertIsNotNone(link)
        self.assertEqual(get_order_for_guest_token(link.group(1)).pk, order.pk)

    def test_token_rejects_tampering_rotation_and_registered_orders(self):
        order = self.make_order()
        token = make_guest_tracking_token(order)
        with self.assertRaises(Http404):
            get_order_for_guest_token(token + "x")
        order.guest_link_nonce = uuid.uuid4()
        order.save(update_fields=["guest_link_nonce"])
        with self.assertRaises(Http404):
            get_order_for_guest_token(token)
        renewed_token = make_guest_tracking_token(order)

        user = get_user_model().objects.create_user(
            email="registered@example.com", password="test-password", full_name="Buyer",
        )
        order.user = user
        order.save(update_fields=["user"])
        with self.assertRaises(ValueError):
            make_guest_tracking_token(order)
        with self.assertRaises(Http404):
            get_order_for_guest_token(renewed_token)

    def test_signed_in_email_has_no_guest_link_and_wrong_recipient_is_rejected(self):
        user = get_user_model().objects.create_user(
            email="registered@example.com", password="test-password", full_name="Buyer",
        )
        order = self.make_order(user=user)
        message = self.make_message(order)
        _, body = render_email(message)
        self.assertNotIn("/api/v1/orders/track/", body)
        message.recipient = "other@example.com"
        with self.assertRaises(PermanentEmailError):
            render_email(message)
