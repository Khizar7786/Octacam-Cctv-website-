from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.models import AuditEvent
from apps.catalog.models import Brand, Category, Product


class ProductDraftApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(
            email="staff-products@example.com", password="test-password", full_name="Staff", is_staff=True,
        )
        cls.customer = get_user_model().objects.create_user(
            email="customer-products@example.com", password="test-password", full_name="Customer",
        )
        cls.brand = Brand.objects.create(name="Hikvision", slug="hikvision")
        cls.category = Category.objects.create(name="Cameras", slug="cameras")

    def setUp(self):
        self.client = APIClient()

    def authorize(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")

    def payload(self, **changes):
        data = {
            "brand": self.brand.id,
            "category": self.category.id,
            "sku": "DS-2CE16D0T-ITP",
            "slug": "hikvision-ds-2ce16d0t-itp",
            "name": "Hikvision Example Camera",
            "short_description": "A draft camera description for API tests.",
            "full_description": "Detailed draft copy supplied for the test product.",
            "regular_price": "12500.00",
            "sale_price": "11999.00",
            "warranty_text": "Test warranty wording.",
        }
        data.update(changes)
        return data

    def create_product(self, **changes):
        return Product.objects.create(
            brand=self.brand,
            category=self.category,
            sku=changes.pop("sku", "EXISTING-SKU"),
            slug=changes.pop("slug", "existing-product"),
            name=changes.pop("name", "Existing Product"),
            short_description=changes.pop("short_description", "Short description"),
            full_description=changes.pop("full_description", "Full description"),
            regular_price=changes.pop("regular_price", Decimal("100.00")),
            sale_price=changes.pop("sale_price", None),
            **changes,
        )

    def test_staff_creates_unpublished_zero_stock_draft(self):
        self.authorize(self.staff)
        response = self.client.post("/api/v1/staff/catalog/products/", self.payload(), format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["sku"], "DS-2CE16D0T-ITP")
        self.assertEqual(response.data["selling_price"], "11999.00")
        self.assertFalse(response.data["is_published"])
        self.assertEqual(response.data["stock_quantity"], 0)
        product = Product.objects.get(pk=response.data["id"])
        self.assertFalse(product.is_published)
        self.assertEqual(product.stock_quantity, 0)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_staff_can_list_retrieve_and_edit_drafts(self):
        product = self.create_product()
        self.authorize(self.staff)
        listing = self.client.get("/api/v1/staff/catalog/products/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data["count"], 1)
        detail_url = f"/api/v1/staff/catalog/products/{product.id}/"
        self.assertEqual(self.client.get(detail_url).data["sku"], "EXISTING-SKU")
        changed = self.client.patch(
            detail_url,
            {"name": "Edited Draft", "warranty_text": "Updated supplied warranty."},
            format="json",
        )
        self.assertEqual(changed.status_code, 200)
        product.refresh_from_db()
        self.assertEqual(product.name, "Edited Draft")
        self.assertEqual(product.warranty_text, "Updated supplied warranty.")
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_staff_routes_reject_visitors_and_customers_without_changes(self):
        product = self.create_product()
        for user, expected, code in (
            (None, 401, "AUTHENTICATION_REQUIRED"),
            (self.customer, 403, "PERMISSION_DENIED"),
        ):
            with self.subTest(expected=expected):
                self.client.credentials()
                if user:
                    self.authorize(user)
                collection = "/api/v1/staff/catalog/products/"
                self.assertEqual(self.client.get(collection).status_code, expected)
                creation = self.client.post(collection, self.payload(sku="NEW", slug="new"), format="json")
                self.assertEqual(creation.status_code, expected)
                update = self.client.patch(
                    f"{collection}{product.id}/", {"regular_price": "80.00"}, format="json",
                )
                self.assertEqual(update.status_code, expected)
                self.assertEqual(update.data["error"]["code"], code)
                product.refresh_from_db()
                self.assertEqual(product.regular_price, Decimal("100.00"))
                self.assertEqual(Product.objects.count(), 1)
                self.assertEqual(AuditEvent.objects.count(), 0)

    def test_invalid_prices_return_field_errors_and_do_not_write(self):
        self.authorize(self.staff)
        invalid_prices = (
            ({"regular_price": "-0.01", "sale_price": None}, "regular_price"),
            ({"regular_price": "100.00", "sale_price": "-0.01"}, "sale_price"),
            ({"regular_price": "100.00", "sale_price": "100.00"}, "sale_price"),
            ({"regular_price": "100.00", "sale_price": "101.00"}, "sale_price"),
            ({"regular_price": "100.001", "sale_price": None}, "regular_price"),
            ({"regular_price": "10000000000.00", "sale_price": None}, "regular_price"),
        )
        for prices, field in invalid_prices:
            with self.subTest(prices=prices):
                response = self.client.post(
                    "/api/v1/staff/catalog/products/", self.payload(**prices), format="json",
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
                self.assertIn(field, response.data["error"]["fields"])
        self.assertEqual(Product.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_price_update_validates_combined_existing_and_submitted_values(self):
        product = self.create_product(regular_price=Decimal("100.00"), sale_price=Decimal("80.00"))
        self.authorize(self.staff)
        url = f"/api/v1/staff/catalog/products/{product.id}/"
        for patch in ({"regular_price": "75.00"}, {"sale_price": "100.00"}):
            response = self.client.patch(url, patch, format="json")
            self.assertEqual(response.status_code, 400)
            self.assertIn("sale_price", response.data["error"]["fields"])
        product.refresh_from_db()
        self.assertEqual(product.regular_price, Decimal("100.00"))
        self.assertEqual(product.sale_price, Decimal("80.00"))
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_duplicate_sku_and_slug_are_case_insensitive_on_create_and_update(self):
        existing = self.create_product(sku="MODEL-ABC", slug="model-abc")
        other = self.create_product(sku="MODEL-OTHER", slug="model-other", name="Other")
        self.authorize(self.staff)
        collection = "/api/v1/staff/catalog/products/"
        for payload, field in (
            (self.payload(sku=" model-abc ", slug="unique-slug"), "sku"),
            (self.payload(sku="UNIQUE-SKU", slug="MODEL-ABC"), "slug"),
        ):
            response = self.client.post(collection, payload, format="json")
            self.assertEqual(response.status_code, 400)
            self.assertIn(field, response.data["error"]["fields"])
        response = self.client.patch(f"{collection}{other.id}/", {"sku": "model-abc"}, format="json")
        self.assertEqual(response.status_code, 400)
        other.refresh_from_db()
        self.assertEqual(other.sku, "MODEL-OTHER")
        self.assertEqual(Product.objects.count(), 2)
        self.assertTrue(Product.objects.filter(pk=existing.pk).exists())

    def test_price_changes_create_actor_attributed_audit_history(self):
        product = self.create_product(regular_price=Decimal("100.00"), sale_price=None)
        self.authorize(self.staff)
        response = self.client.patch(
            f"/api/v1/staff/catalog/products/{product.id}/",
            {"regular_price": "120.00", "sale_price": "110.00"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        event = AuditEvent.objects.get()
        self.assertEqual(event.actor, self.staff)
        self.assertEqual(event.resource_type, "Product")
        self.assertEqual(event.resource_id, str(product.id))
        self.assertEqual(event.action, "PRODUCT_PRICE_CHANGED")
        self.assertEqual(event.before_data, {"regular_price": "100.00", "sale_price": None})
        self.assertEqual(event.after_data, {"regular_price": "120.00", "sale_price": "110.00"})

    def test_publication_and_stock_fields_are_rejected_and_no_delete_route_exists(self):
        product = self.create_product()
        self.authorize(self.staff)
        collection = "/api/v1/staff/catalog/products/"
        creation = self.client.post(
            collection, self.payload(sku="NEW", slug="new", is_published=True, stock_quantity=10), format="json",
        )
        self.assertEqual(creation.status_code, 400)
        self.assertIn("is_published", creation.data["error"]["fields"])
        self.assertIn("stock_quantity", creation.data["error"]["fields"])
        update = self.client.patch(
            f"{collection}{product.id}/", {"is_published": True, "stock_quantity": 10}, format="json",
        )
        self.assertEqual(update.status_code, 400)
        self.assertEqual(self.client.delete(f"{collection}{product.id}/").status_code, 405)
        product.refresh_from_db()
        self.assertFalse(product.is_published)
        self.assertEqual(product.stock_quantity, 0)

    def test_database_constraints_reject_invalid_prices_outside_api(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create_product(regular_price=Decimal("100.00"), sale_price=Decimal("100.00"))
