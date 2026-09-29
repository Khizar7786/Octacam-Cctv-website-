import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Event
from unittest.mock import patch
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.db import close_old_connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.models import AuditEvent
from apps.catalog.models import Brand, Category, InventoryMovement, Product
from apps.communications.models import EmailOutbox
from apps.communications.services import process_email_batch
from apps.orders.models import Order, OrderItem
from apps.orders.services import CheckoutConflict, create_quote, place_order


CHECKOUT_SETTINGS = override_settings(
    CHECKOUT_SHIPPING_FEE="250.00", CHECKOUT_TAX_RATE_PERCENT="10.00",
    CHECKOUT_SHIPPING_TAXABLE="false", EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)


def make_product(*, stock=2, regular="1000.00", sale="900.00"):
    brand = Brand.objects.create(name="Checkout Brand", slug="checkout-brand")
    category = Category.objects.create(name="Checkout Cameras", slug="checkout-cameras")
    return Product.objects.create(
        brand=brand, category=category, name="Checkout Camera", sku="CHECK-1", slug="checkout-camera",
        short_description="Camera", full_description="Camera", regular_price=regular,
        sale_price=sale, stock_quantity=stock, is_published=True,
    )


def cart(product, quantity=1):
    return {"items": [{"product_id": product.pk, "quantity": quantity}],
            "delivery_city": "Lahore", "delivery_province": "Punjab"}


def place_data(product, token, quantity=1):
    return {
        **cart(product, quantity), "quote_token": token,
        "customer_name": "A Buyer", "customer_email": "buyer@example.com", "customer_phone": "03001234567",
        "delivery_address_line1": "12 Camera Street", "delivery_address_line2": "Floor 2",
        "delivery_postal_code": "54000", "delivery_country": "PK",
    }


@CHECKOUT_SETTINGS
class CheckoutApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.product = make_product()
        cls.customer = get_user_model().objects.create_user(
            email="customer@example.com", password="test-password", full_name="Customer",
        )

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def quote(self, quantity=1):
        return self.client.post("/api/v1/checkout/quote/", cart(self.product, quantity), format="json")

    def place(self, data, key=None):
        return self.client.post(
            "/api/v1/checkout/place/", data, format="json",
            HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()),
        )

    def test_guest_quote_place_snapshots_stock_history_outbox_and_tracking(self):
        quoted = self.quote(quantity=2)
        self.assertEqual(quoted.status_code, 200, quoted.data)
        self.assertEqual(quoted.data["subtotal"], "1800.00")
        self.assertEqual(quoted.data["shipping_fee"], "250.00")
        self.assertEqual(quoted.data["tax_total"], "180.00")
        self.assertEqual(quoted.data["grand_total"], "2230.00")
        self.assertEqual(quoted.data["items"][0]["sale_savings"], "200.00")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 2, "A quote must not reserve stock")

        placed = self.place(place_data(self.product, quoted.data["quote_token"], quantity=2))
        self.assertEqual(placed.status_code, 201, placed.data)
        self.assertEqual(placed.data["status"], "placed")
        self.assertEqual(placed.data["payment_method"], "COD")
        self.assertEqual(placed.data["payment_status"], "uncollected")
        self.assertEqual(placed.data["delivery_address_line1"], "12 Camera Street")
        self.assertEqual(placed.data["grand_total"], "2230.00")
        order = Order.objects.get()
        self.assertIsNone(order.user_id)
        self.assertEqual(order.delivery_country, "PK")
        self.assertEqual((order.subtotal, order.tax_total, order.shipping_fee, order.grand_total),
                         (Decimal("1800.00"), Decimal("180.00"), Decimal("250.00"), Decimal("2230.00")))
        item = OrderItem.objects.get()
        self.assertEqual((item.product_name, item.sku, item.unit_price, item.quantity),
                         ("Checkout Camera", "CHECK-1", Decimal("900.00"), 2))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 0)
        movement = InventoryMovement.objects.get()
        self.assertEqual((movement.reason, movement.quantity_delta, movement.previous_quantity,
                          movement.new_quantity, movement.order_id), ("order_placed", -2, 2, 0, order.pk))
        self.assertEqual(AuditEvent.objects.get().action, "ORDER_PLACED")
        event = EmailOutbox.objects.get()
        self.assertEqual((event.event_type, event.status, event.order_id), ("ORDER_PLACED", "pending", order.pk))

        tracking = self.client.get(urlsplit(placed.data["guest_tracking_url"]).path)
        self.assertEqual(tracking.status_code, 200, tracking.data)
        self.assertEqual(tracking.data["reference"], order.reference)
        self.assertNotIn("customer_email", tracking.data)
        self.assertNotIn("delivery_address_line1", tracking.data)
        self.assertEqual(self.client.get("/api/v1/orders/track/invalid/").status_code, 404)
        self.assertEqual(process_email_batch(), ["sent"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(order.reference, mail.outbox[0].subject)

        Product.objects.filter(pk=self.product.pk).update(name="Renamed", sku="RENAMED", regular_price="1200.00")
        item.refresh_from_db()
        self.assertEqual((item.product_name, item.sku, item.unit_price),
                         ("Checkout Camera", "CHECK-1", Decimal("900.00")))

    def test_idempotent_retry_and_conflicting_reuse(self):
        token = self.quote().data["quote_token"]
        payload = place_data(self.product, token)
        key = uuid.uuid4()
        first = self.place(payload, key)
        self.assertEqual(first.status_code, 201, first.data)
        second = self.place(payload, key)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(second.data["public_id"], first.data["public_id"])
        changed = {**payload, "customer_name": "Different Buyer"}
        conflict = self.place(changed, key)
        self.assertEqual(conflict.status_code, 409, conflict.data)
        self.assertEqual(conflict.data["error"]["code"], "IDEMPOTENCY_CONFLICT")
        self.assertEqual((Order.objects.count(), OrderItem.objects.count(), InventoryMovement.objects.count(),
                          EmailOutbox.objects.count()), (1, 1, 1, 1))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 1)

    def test_changed_price_and_configuration_require_new_review(self):
        original = self.quote().data["quote_token"]
        Product.objects.filter(pk=self.product.pk).update(sale_price="800.00")
        changed = self.place(place_data(self.product, original))
        self.assertEqual(changed.status_code, 409, changed.data)
        self.assertEqual(changed.data["error"]["code"], "CHECKOUT_CHANGED")
        self.assertEqual(changed.data["current_quote"]["grand_total"], "1130.00")
        self.assertFalse(Order.objects.exists())
        with override_settings(CHECKOUT_SHIPPING_FEE="300.00"):
            changed_again = self.place(place_data(self.product, changed.data["current_quote"]["quote_token"]))
        self.assertEqual(changed_again.status_code, 409, changed_again.data)
        self.assertEqual(changed_again.data["current_quote"]["shipping_fee"], "300.00")
        self.assertFalse(Order.objects.exists())

    def test_explicit_tax_on_shipping_is_itemized_and_tax_changes_require_review(self):
        initial = self.quote()
        with override_settings(CHECKOUT_TAX_RATE_PERCENT="7.50", CHECKOUT_SHIPPING_TAXABLE="true"):
            changed = self.place(place_data(self.product, initial.data["quote_token"]))
            self.assertEqual(changed.status_code, 409, changed.data)
            current = changed.data["current_quote"]
            self.assertEqual(current["items"][0]["tax_amount"], "67.50")
            self.assertEqual(current["shipping_tax_amount"], "18.75")
            self.assertEqual(current["tax_total"], "86.25")
            self.assertEqual(current["grand_total"], "1236.25")
            placed = self.place(place_data(self.product, current["quote_token"]))
            self.assertEqual(placed.status_code, 201, placed.data)
        order = Order.objects.get()
        self.assertEqual(order.tax_rate_percent, Decimal("7.50"))
        self.assertTrue(order.shipping_taxable)
        self.assertEqual(order.shipping_tax_amount, Decimal("18.75"))

    def test_unavailable_product_and_unsupported_survey_are_rejected(self):
        token = self.quote().data["quote_token"]
        Product.objects.filter(pk=self.product.pk).update(stock_quantity=0)
        changed = self.place(place_data(self.product, token))
        self.assertEqual(changed.status_code, 409, changed.data)
        self.assertEqual(changed.data["error"]["code"], "CHECKOUT_CHANGED")
        self.assertIsNone(changed.data["current_quote"]["quote_token"])
        self.assertEqual(self.quote().data["error"]["code"], "OUT_OF_STOCK")
        self.assertFalse(Order.objects.exists())

        payload = place_data(self.product, token)
        payload["survey"] = {"slot_id": 1}
        unsupported = self.place(payload)
        self.assertEqual(unsupported.status_code, 400)
        self.assertIn("survey", unsupported.data["error"]["fields"])

    def test_unpublished_after_quote_needs_review(self):
        token = self.quote().data["quote_token"]
        Product.objects.filter(pk=self.product.pk).update(is_published=False)
        response = self.place(place_data(self.product, token))
        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(response.data["error"]["code"], "CHECKOUT_CHANGED")
        self.assertIsNone(response.data["current_quote"])
        self.assertFalse(Order.objects.exists())

    def test_inactive_brand_or_category_cannot_be_purchased(self):
        token = self.quote().data["quote_token"]
        Brand.objects.filter(pk=self.product.brand_id).update(is_active=False)
        response = self.place(place_data(self.product, token))
        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(response.data["error"]["code"], "CHECKOUT_CHANGED")
        self.assertEqual(self.quote().status_code, 400)
        Brand.objects.filter(pk=self.product.brand_id).update(is_active=True)
        Category.objects.filter(pk=self.product.category_id).update(is_active=False)
        self.assertEqual(self.quote().status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_signed_in_order_and_passwordless_guest_request_rules(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(self.customer).access_token}")
        token = self.quote().data["quote_token"]
        placed = self.place(place_data(self.product, token))
        self.assertEqual(placed.status_code, 201, placed.data)
        self.assertIsNone(placed.data["guest_tracking_url"])
        self.assertEqual(Order.objects.get().user_id, self.customer.pk)

    def test_bad_requests_and_missing_business_configuration(self):
        bad_items = self.client.post("/api/v1/checkout/quote/", {
            **cart(self.product), "items": [{"product_id": self.product.pk, "quantity": 1}] * 2,
        }, format="json")
        self.assertEqual(bad_items.status_code, 400)
        self.assertIn("items", bad_items.data["error"]["fields"])
        token = self.quote().data["quote_token"]
        bad_token = self.place(place_data(self.product, token + "x"))
        self.assertEqual(bad_token.status_code, 400)
        self.assertIn("quote_token", bad_token.data["error"]["fields"])
        missing_key = self.client.post("/api/v1/checkout/place/", place_data(self.product, token), format="json")
        self.assertEqual(missing_key.status_code, 400)
        invalid_country = self.place({**place_data(self.product, token), "delivery_country": "US"})
        self.assertEqual(invalid_country.status_code, 400)
        with override_settings(CHECKOUT_SHIPPING_FEE=None):
            unavailable = self.quote()
        self.assertEqual(unavailable.status_code, 503, unavailable.data)
        self.assertEqual(unavailable.data["error"]["code"], "CHECKOUT_NOT_CONFIGURED")

    def test_email_failure_does_not_undo_committed_order(self):
        token = self.quote().data["quote_token"]
        placed = self.place(place_data(self.product, token))
        self.assertEqual(placed.status_code, 201)
        with patch("apps.communications.services.deliver_email", side_effect=OSError("offline")):
            self.assertEqual(process_email_batch(), ["failed"])
        self.assertEqual(Order.objects.count(), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 1)
        event = EmailOutbox.objects.get()
        self.assertEqual(event.status, "failed")
        self.assertEqual(event.attempt_count, 1)

    def test_outbox_creation_failure_rolls_back_order_and_stock(self):
        token = self.quote().data["quote_token"]
        with patch("apps.orders.services.enqueue_email", side_effect=RuntimeError("outbox unavailable")):
            with self.assertRaises(RuntimeError):
                self.place(place_data(self.product, token))
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(InventoryMovement.objects.count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 2)

    def test_csrf_is_required_for_guest_quote_and_place(self):
        browser = APIClient(enforce_csrf_checks=True)
        csrf_token = browser.get("/api/v1/auth/csrf/").data["csrfToken"]
        self.assertEqual(browser.post("/api/v1/checkout/quote/", cart(self.product), format="json").status_code, 403)
        quoted = browser.post(
            "/api/v1/checkout/quote/", cart(self.product), format="json", HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(quoted.status_code, 200, quoted.data)
        payload = place_data(self.product, quoted.data["quote_token"])
        self.assertEqual(browser.post(
            "/api/v1/checkout/place/", payload, format="json", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        ).status_code, 403)
        self.assertFalse(Order.objects.exists())


@CHECKOUT_SETTINGS
class CheckoutConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.product = make_product(stock=1)
        self.quote = create_quote(cart(self.product))
        self.data = place_data(self.product, self.quote["quote_token"])

    def test_last_unit_is_sold_once_and_loser_gets_updated_state(self):
        first_created = Event()
        release_first = Event()
        second_started = Event()
        second_done = Event()

        def first():
            close_old_connections()
            try:
                with transaction.atomic():
                    order, _ = place_order(data=self.data, idempotency_key=uuid.uuid4(), user=None)
                    first_created.set()
                    if not release_first.wait(10):
                        raise AssertionError("Timed out waiting to release first checkout")
                    return order.pk
            finally:
                close_old_connections()

        def second():
            close_old_connections()
            try:
                second_started.set()
                try:
                    place_order(data=self.data, idempotency_key=uuid.uuid4(), user=None)
                except CheckoutConflict as exc:
                    return exc.code
                return "unexpected_success"
            finally:
                second_done.set()
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            future_first = pool.submit(first)
            try:
                self.assertTrue(first_created.wait(10))
                future_second = pool.submit(second)
                self.assertTrue(second_started.wait(10))
                self.assertFalse(second_done.wait(0.2), "Second checkout bypassed the product row lock")
            finally:
                release_first.set()
            first_id = future_first.result(timeout=10)
            result_second = future_second.result(timeout=10)
        self.assertEqual(result_second, "CHECKOUT_CHANGED")
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(Order.objects.get().pk, first_id)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 0)
        self.assertEqual(InventoryMovement.objects.count(), 1)
        self.assertEqual(EmailOutbox.objects.count(), 1)

    def test_same_key_concurrent_retry_returns_existing_order(self):
        first_created = Event()
        release_first = Event()
        second_started = Event()
        second_done = Event()
        key = uuid.uuid4()

        def first():
            close_old_connections()
            try:
                with transaction.atomic():
                    order, created = place_order(data=self.data, idempotency_key=key, user=None)
                    first_created.set()
                    if not release_first.wait(10):
                        raise AssertionError("Timed out waiting to release first checkout")
                    return order.pk, created
            finally:
                close_old_connections()

        def second():
            close_old_connections()
            try:
                second_started.set()
                return place_order(data=self.data, idempotency_key=key, user=None)
            finally:
                second_done.set()
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            future_first = pool.submit(first)
            try:
                self.assertTrue(first_created.wait(10))
                future_second = pool.submit(second)
                self.assertTrue(second_started.wait(10))
                self.assertFalse(second_done.wait(0.2), "Retry did not wait for the first checkout")
            finally:
                release_first.set()
            first_id, first_created_flag = future_first.result(timeout=10)
            second_order, second_created_flag = future_second.result(timeout=10)
        self.assertTrue(first_created_flag)
        self.assertEqual(second_order.pk, first_id)
        self.assertFalse(second_created_flag)
        self.assertEqual((Order.objects.count(), InventoryMovement.objects.count(), EmailOutbox.objects.count()),
                         (1, 1, 1))

    def test_same_key_different_carts_cannot_create_two_orders(self):
        second_product = Product.objects.create(
            brand=self.product.brand, category=self.product.category,
            name="Second Camera", sku="CHECK-2", slug="second-camera",
            short_description="Camera", full_description="Camera", regular_price="1000.00",
            stock_quantity=1, is_published=True,
        )
        other_quote = create_quote(cart(second_product))
        other_data = place_data(second_product, other_quote["quote_token"])
        first_created = Event()
        release_first = Event()
        second_started = Event()
        second_done = Event()
        key = uuid.uuid4()

        def first():
            close_old_connections()
            try:
                with transaction.atomic():
                    order, _ = place_order(data=self.data, idempotency_key=key, user=None)
                    first_created.set()
                    if not release_first.wait(10):
                        raise AssertionError("Timed out waiting to release first checkout")
                    return order.pk
            finally:
                close_old_connections()

        def second():
            close_old_connections()
            try:
                second_started.set()
                try:
                    place_order(data=other_data, idempotency_key=key, user=None)
                except CheckoutConflict as exc:
                    return exc.code
                return "unexpected_success"
            finally:
                second_done.set()
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            future_first = pool.submit(first)
            try:
                self.assertTrue(first_created.wait(10))
                future_second = pool.submit(second)
                self.assertTrue(second_started.wait(10))
                self.assertFalse(second_done.wait(0.2), "Unique idempotency key was bypassed")
            finally:
                release_first.set()
            future_first.result(timeout=10)
            self.assertEqual(future_second.result(timeout=10), "IDEMPOTENCY_CONFLICT")
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(InventoryMovement.objects.count(), 1)
        second_product.refresh_from_db()
        self.assertEqual(second_product.stock_quantity, 1)

    def test_brand_deactivation_waits_for_inflight_checkout(self):
        order_created = Event()
        release_order = Event()
        deactivation_started = Event()
        deactivation_done = Event()

        def checkout():
            close_old_connections()
            try:
                with transaction.atomic():
                    order, _ = place_order(data=self.data, idempotency_key=uuid.uuid4(), user=None)
                    order_created.set()
                    if not release_order.wait(10):
                        raise AssertionError("Timed out waiting to release checkout")
                    return order.pk
            finally:
                close_old_connections()

        def deactivate():
            close_old_connections()
            try:
                deactivation_started.set()
                Brand.objects.filter(pk=self.product.brand_id).update(is_active=False)
            finally:
                deactivation_done.set()
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            order_future = pool.submit(checkout)
            try:
                self.assertTrue(order_created.wait(10))
                deactivate_future = pool.submit(deactivate)
                self.assertTrue(deactivation_started.wait(10))
                self.assertFalse(deactivation_done.wait(0.2), "Brand deactivation bypassed the checkout lock")
            finally:
                release_order.set()
            order_future.result(timeout=10)
            deactivate_future.result(timeout=10)
        self.assertEqual(Order.objects.count(), 1)
        self.assertFalse(Brand.objects.get(pk=self.product.brand_id).is_active)
