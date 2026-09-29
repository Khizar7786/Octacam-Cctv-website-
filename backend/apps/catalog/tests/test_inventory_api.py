from concurrent.futures import ThreadPoolExecutor
from threading import Event

from django.contrib.auth import get_user_model
from django.db import IntegrityError, close_old_connections, transaction
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.models import AuditEvent
from apps.catalog.inventory_services import adjust_product_stock
from apps.catalog.models import Brand, Category, InventoryMovement, Product


def create_product(*, stock=0, published=False):
    brand = Brand.objects.create(name="Inventory Brand", slug="inventory-brand")
    category = Category.objects.create(name="Cameras", slug="cameras")
    return Product.objects.create(
        brand=brand, category=category, sku="INV-001", slug="inventory-camera", name="Inventory Camera",
        short_description="Stock test", full_description="Stock test product", regular_price="100.00",
        stock_quantity=stock, is_published=published,
    )


class InventoryApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(
            email="stock-staff@example.com", password="test-password", full_name="Staff", is_staff=True,
        )
        cls.customer = get_user_model().objects.create_user(
            email="stock-customer@example.com", password="test-password", full_name="Customer",
        )
        cls.product = create_product(published=True)

    def setUp(self):
        self.client = APIClient()
        self.url = f"/api/v1/staff/catalog/products/{self.product.pk}/stock-adjustments/"

    def authorize(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")

    def test_staff_adjusts_stock_and_reads_paginated_history(self):
        self.authorize(self.staff)
        first = self.client.post(self.url, {"new_quantity": 7, "reason": "  Received counted stock  "}, format="json")
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(first.data["previous_quantity"], 0)
        self.assertEqual(first.data["new_quantity"], 7)
        self.assertEqual(first.data["quantity_delta"], 7)
        self.assertEqual(first.data["movement_type"], "manual_adjustment")
        self.assertEqual(first.data["reason"], "Received counted stock")
        self.assertEqual(first.data["actor"], self.staff.pk)
        second = self.client.post(self.url, {"new_quantity": 2, "reason": "Physical count correction"}, format="json")
        self.assertEqual(second.status_code, 201, second.data)
        self.assertEqual(second.data["previous_quantity"], 7)
        self.assertEqual(second.data["quantity_delta"], -5)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 2)

        history = self.client.get(self.url)
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.data["count"], 2)
        self.assertEqual([row["id"] for row in history.data["results"]], [second.data["id"], first.data["id"]])
        self.assertEqual(self.client.get("/api/v1/catalog/products/inventory-camera/").data["stock_quantity"], 2)
        events = list(AuditEvent.objects.order_by("created_at", "id"))
        self.assertEqual([event.action for event in events], ["PRODUCT_STOCK_ADJUSTED"] * 2)
        self.assertEqual(events[0].before_data, {"stock_quantity": 0})
        self.assertEqual(events[0].after_data, {"stock_quantity": 7})
        self.assertEqual(events[0].metadata["reason"], "Received counted stock")
        self.assertEqual(events[1].metadata["inventory_movement_id"], second.data["id"])

    def test_stock_routes_require_staff_and_hide_history(self):
        self.authorize(self.staff)
        self.client.post(self.url, {"new_quantity": 3, "reason": "Initial count"}, format="json")
        for user, expected in ((None, 401), (self.customer, 403)):
            with self.subTest(user=user):
                self.client.credentials()
                if user:
                    self.authorize(user)
                self.assertEqual(self.client.get(self.url).status_code, expected)
                self.assertEqual(self.client.post(
                    self.url, {"new_quantity": 4, "reason": "Unauthorized"}, format="json",
                ).status_code, expected)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 3)
        self.assertEqual(InventoryMovement.objects.count(), 1)

    def test_invalid_adjustments_and_generic_product_edit_do_not_change_stock(self):
        self.authorize(self.staff)
        for payload, field in (
            ({"new_quantity": -1, "reason": "Count"}, "new_quantity"),
            ({"new_quantity": 2, "reason": "   "}, "reason"),
            ({"new_quantity": 0, "reason": "No change"}, "new_quantity"),
            ({"new_quantity": 2_147_483_648, "reason": "Count"}, "new_quantity"),
        ):
            with self.subTest(payload=payload):
                response = self.client.post(self.url, payload, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data["error"]["fields"])
        direct_edit = self.client.patch(
            f"/api/v1/staff/catalog/products/{self.product.pk}/",
            {"stock_quantity": 5}, format="json",
        )
        self.assertEqual(direct_edit.status_code, 400)
        self.assertIn("stock_quantity", direct_edit.data["error"]["fields"])
        self.assertEqual(self.client.post(
            "/api/v1/staff/catalog/products/999999/stock-adjustments/",
            {"new_quantity": 1, "reason": "Missing"}, format="json",
        ).status_code, 404)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 0)
        self.assertEqual(InventoryMovement.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_stock_and_movement_database_constraints(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Product.objects.filter(pk=self.product.pk).update(stock_quantity=-1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            InventoryMovement.objects.create(
                product=self.product, quantity_delta=2, previous_quantity=0, new_quantity=1,
                reason=InventoryMovement.Reason.MANUAL_ADJUSTMENT, note="Invalid", actor=self.staff,
            )

    def test_audit_failure_rolls_back_stock_and_movement(self):
        from unittest.mock import patch

        self.authorize(self.staff)
        with patch("apps.catalog.inventory_services.record_audit_event", side_effect=RuntimeError("audit unavailable")):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url, {"new_quantity": 4, "reason": "Count"}, format="json")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 0)
        self.assertFalse(InventoryMovement.objects.exists())


class InventoryConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            email="concurrent-staff@example.com", password="test-password", full_name="Staff", is_staff=True,
        )
        self.product = create_product(stock=4)

    def test_two_adjustments_serialize_and_history_uses_latest_quantity(self):
        first_written = Event()
        release_first = Event()
        second_started = Event()
        second_done = Event()

        def first_adjustment():
            close_old_connections()
            try:
                with transaction.atomic():
                    movement = adjust_product_stock(
                        product_id=self.product.pk, new_quantity=7, reason="First count", actor=self.staff,
                    )
                    first_written.set()
                    if not release_first.wait(10):
                        raise AssertionError("Timed out waiting to release the first transaction")
                    return movement.pk
            finally:
                close_old_connections()

        def second_adjustment():
            close_old_connections()
            try:
                second_started.set()
                return adjust_product_stock(
                    product_id=self.product.pk, new_quantity=2, reason="Second count", actor=self.staff,
                ).pk
            finally:
                second_done.set()
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(first_adjustment)
            try:
                self.assertTrue(first_written.wait(10))
                second = pool.submit(second_adjustment)
                self.assertTrue(second_started.wait(10))
                self.assertFalse(second_done.wait(0.2), "Second adjustment bypassed the product row lock")
            finally:
                release_first.set()
            first_id = first.result(timeout=10)
            second_id = second.result(timeout=10)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 2)
        first_movement = InventoryMovement.objects.get(pk=first_id)
        second_movement = InventoryMovement.objects.get(pk=second_id)
        self.assertEqual((first_movement.previous_quantity, first_movement.new_quantity), (4, 7))
        self.assertEqual((second_movement.previous_quantity, second_movement.new_quantity), (7, 2))
        self.assertEqual(InventoryMovement.objects.count(), 2)
        self.assertEqual(AuditEvent.objects.count(), 2)
