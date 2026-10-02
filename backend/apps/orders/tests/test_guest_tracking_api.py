import logging
import re
import uuid
from unittest.mock import patch
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail, signing
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.communications.models import EmailOutbox
from apps.communications.services import process_one_email
from apps.orders.logging import RedactGuestTrackingToken
from apps.orders.models import Order
from apps.orders.tracking import GUEST_TRACKING_SALT, build_guest_tracking_url
from apps.orders.tests.test_checkout_api import CHECKOUT_SETTINGS, cart, make_product, place_data


@CHECKOUT_SETTINGS
class GuestOrderTrackingApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.product = make_product(stock=3)

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def place_order(self, *, key=None):
        quote = self.client.post("/api/v1/checkout/quote/", cart(self.product), format="json")
        self.assertEqual(quote.status_code, 200, quote.data)
        body = place_data(self.product, quote.data["quote_token"])
        response = self.client.post(
            "/api/v1/checkout/place/", body, format="json",
            HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()),
        )
        self.assertEqual(response.status_code, 201, response.data)
        return response, body

    def assert_private(self, response):
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["Referrer-Policy"], "no-referrer")
        self.assertIn("noindex", response["X-Robots-Tag"])

    def test_receipt_works_before_email_and_after_failed_delivery(self):
        receipt, _ = self.place_order()
        self.assert_private(receipt)
        link = receipt.data["guest_tracking_url"]
        self.assertTrue(link.startswith(f"{settings.PUBLIC_SITE_URL}/api/v1/orders/track/"))

        tracked = self.client.get(urlsplit(link).path)
        self.assertEqual(tracked.status_code, 200, tracked.data)
        self.assert_private(tracked)
        self.assertEqual(tracked.data["reference"], receipt.data["reference"])
        self.assertEqual(tracked.data["grand_total"], receipt.data["grand_total"])

        with patch("apps.communications.services.deliver_email", side_effect=RuntimeError("SMTP unavailable")):
            self.assertEqual(process_one_email(), "failed")
        message = EmailOutbox.objects.get()
        self.assertEqual(message.status, EmailOutbox.Status.FAILED)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(self.client.get(urlsplit(link).path).status_code, 200)

        EmailOutbox.objects.filter(pk=message.pk).update(next_attempt_at=timezone.now())
        self.assertEqual(process_one_email(), "sent")
        email_link = re.search(r"https?://[^\s]+/api/v1/orders/track/[^\s/]+/", mail.outbox[0].body)
        self.assertIsNotNone(email_link)
        self.assertEqual(email_link.group(), link)

    def test_idempotent_retry_returns_identical_private_link(self):
        key = uuid.uuid4()
        quote = self.client.post("/api/v1/checkout/quote/", cart(self.product), format="json")
        self.assertEqual(quote.status_code, 200, quote.data)
        body = place_data(self.product, quote.data["quote_token"])
        with patch("django.core.signing.TimestampSigner.timestamp", return_value="1"):
            receipt = self.client.post(
                "/api/v1/checkout/place/", body, format="json", HTTP_IDEMPOTENCY_KEY=str(key),
            )
        self.assertEqual(receipt.status_code, 201, receipt.data)
        with patch("django.core.signing.TimestampSigner.timestamp", return_value="2"):
            retry = self.client.post(
                "/api/v1/checkout/place/", body, format="json", HTTP_IDEMPOTENCY_KEY=str(key),
            )
        self.assertEqual(retry.status_code, 200, retry.data)
        self.assert_private(retry)
        self.assertEqual(retry.data, receipt.data)
        self.assertEqual(EmailOutbox.objects.count(), 1)

    def test_invalid_reference_and_mismatched_tokens_have_same_404(self):
        first, _ = self.place_order()
        second, _ = self.place_order()
        first_order = Order.objects.get(reference=first.data["reference"])
        second_order = Order.objects.get(reference=second.data["reference"])
        token = urlsplit(first.data["guest_tracking_url"]).path.split("/")[-2]
        tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
        signer = signing.Signer(salt=GUEST_TRACKING_SALT)
        unknown_order = signer.sign_object({"public_id": str(uuid.uuid4()), "nonce": str(uuid.uuid4())})
        wrong_nonce = signer.sign_object({"public_id": str(first_order.public_id), "nonce": str(uuid.uuid4())})
        mixed_orders = signer.sign_object({
            "public_id": str(first_order.public_id), "nonce": str(second_order.guest_link_nonce),
        })
        paths = [first_order.reference, tampered, unknown_order, wrong_nonce, mixed_orders, "invalid"]
        errors = []
        for candidate in paths:
            response = self.client.get(f"/api/v1/orders/track/{candidate}/")
            self.assertEqual(response.status_code, 404, response.data)
            self.assert_private(response)
            errors.append(response.data)
        self.assertTrue(all(error == errors[0] for error in errors))

        first_tracking = self.client.get(urlsplit(first.data["guest_tracking_url"]).path)
        second_tracking = self.client.get(urlsplit(second.data["guest_tracking_url"]).path)
        self.assertEqual(first_tracking.data["reference"], first_order.reference)
        self.assertEqual(second_tracking.data["reference"], second_order.reference)

    def test_tracking_response_has_only_status_and_order_snapshots(self):
        receipt, _ = self.place_order()
        tracked = self.client.get(urlsplit(receipt.data["guest_tracking_url"]).path)
        self.assertEqual(set(tracked.data), {
            "reference", "placed_at", "status", "payment_method", "payment_status", "items",
            "subtotal", "tax_total", "shipping_fee", "grand_total", "courier_name",
            "tracking_number", "tracking_url",
        })
        self.assertEqual(set(tracked.data["items"][0]), {
            "product_name", "sku", "quantity", "unit_price", "line_subtotal", "tax_amount",
        })
        for private_value in ("A Buyer", "buyer@example.com", "03001234567", "12 Camera Street"):
            self.assertNotIn(private_value, str(tracked.data))
        self.assertNotIn("guest_tracking_url", tracked.data)
        self.assertNotIn("public_id", tracked.data)

    def test_nonce_rotation_revokes_old_link_and_legacy_link_remains_readable(self):
        receipt, _ = self.place_order()
        order = Order.objects.get()
        old_path = urlsplit(receipt.data["guest_tracking_url"]).path
        legacy_token = signing.dumps(
            {"public_id": str(order.public_id), "nonce": str(order.guest_link_nonce)},
            salt=GUEST_TRACKING_SALT,
        )
        self.assertEqual(self.client.get(f"/api/v1/orders/track/{legacy_token}/").status_code, 200)

        order.guest_link_nonce = uuid.uuid4()
        order.save(update_fields=["guest_link_nonce"])
        revoked = self.client.get(old_path)
        self.assertEqual(revoked.status_code, 404)
        self.assert_private(revoked)
        self.assertEqual(self.client.get(f"/api/v1/orders/track/{legacy_token}/").status_code, 404)

        new_link = build_guest_tracking_url(order)
        self.assertNotEqual(new_link, receipt.data["guest_tracking_url"])
        self.assertEqual(self.client.get(urlsplit(new_link).path).status_code, 200)

    def test_signed_in_order_has_no_guest_link_and_cannot_be_tracked_by_signed_payload(self):
        customer = get_user_model().objects.create_user(
            email="customer@example.com", password="test-password", full_name="Customer",
        )
        self.client.force_authenticate(user=customer)
        receipt, _ = self.place_order()
        self.assertIsNone(receipt.data["guest_tracking_url"])
        order = Order.objects.get()
        token = signing.Signer(salt=GUEST_TRACKING_SALT).sign_object({
            "public_id": str(order.public_id), "nonce": str(order.guest_link_nonce),
        })
        self.assertEqual(self.client.get(f"/api/v1/orders/track/{token}/").status_code, 404)

    def test_django_access_logs_redact_the_tracking_token(self):
        receipt, _ = self.place_order()
        path = urlsplit(receipt.data["guest_tracking_url"]).path
        token = path.split("/")[-2]
        record = logging.LogRecord(
            "django.server", logging.INFO, __file__, 1,
            '"GET %s HTTP/1.1" 200 123', (path,), None,
        )
        self.assertTrue(RedactGuestTrackingToken().filter(record))
        self.assertNotIn(token, record.getMessage())
        self.assertIn("/api/v1/orders/track/[REDACTED]/", record.getMessage())
        self.assertTrue(any(
            isinstance(item, RedactGuestTrackingToken)
            for handler in logging.getLogger("django.server").handlers
            for item in handler.filters
        ))
