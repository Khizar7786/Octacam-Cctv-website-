from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.models import AuditEvent
from apps.catalog.models import (
    Brand,
    Category,
    Product,
    ProductSpecificationValue,
    SpecificationChoice,
    SpecificationDefinition,
)


class SpecificationsAndPublicationApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(
            email="catalog-staff@example.com",
            password="test-password",
            full_name="Catalog Staff",
            is_staff=True,
        )
        cls.customer = get_user_model().objects.create_user(
            email="catalog-customer@example.com",
            password="test-password",
            full_name="Catalog Customer",
        )
        cls.brand = Brand.objects.create(name="Hikvision", slug="hikvision")
        cls.cameras = Category.objects.create(name="Cameras", slug="cameras")
        cls.storage = Category.objects.create(name="Storage", slug="storage")

    def setUp(self):
        self.client = APIClient()

    def authorize(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")

    def product_payload(self, *, category=None, sku="CAM-001", slug="camera-001", specifications=None):
        payload = {
            "brand": self.brand.id,
            "category": (category or self.cameras).id,
            "sku": sku,
            "slug": slug,
            "name": "Example CCTV Product",
            "short_description": "Accurate short product description.",
            "full_description": "Accurate detailed product description.",
            "regular_price": "12500.00",
            "sale_price": None,
            "warranty_text": "Supplier-provided test warranty.",
        }
        if specifications is not None:
            payload["specifications"] = specifications
        return payload

    def create_required_definitions(self):
        resolution = SpecificationDefinition.objects.create(
            category=self.cameras,
            key="resolution",
            label="Resolution",
            data_type=SpecificationDefinition.DataType.CHOICE,
            is_required=True,
            is_filterable=True,
        )
        SpecificationChoice.objects.create(definition=resolution, value="4mp", label="4 MP")
        capacity = SpecificationDefinition.objects.create(
            category=self.storage,
            key="capacity",
            label="Capacity",
            data_type=SpecificationDefinition.DataType.DECIMAL,
            unit="TB",
            is_required=True,
            is_filterable=True,
        )
        return resolution, capacity

    def test_staff_manages_category_definitions_and_choices(self):
        self.authorize(self.staff)
        camera_url = f"/api/v1/staff/catalog/categories/{self.cameras.id}/specifications/"
        created = self.client.post(camera_url, {
            "key": "resolution",
            "label": "Resolution",
            "data_type": "choice",
            "is_required": True,
            "is_filterable": True,
            "is_displayed": True,
            "sort_order": 1,
        }, format="json")
        self.assertEqual(created.status_code, 201)
        definition_id = created.data["id"]
        self.assertEqual(created.data["category"], self.cameras.id)

        choice = self.client.post(
            f"/api/v1/staff/catalog/specifications/{definition_id}/choices/",
            {"value": "4mp", "label": "4 MP", "sort_order": 1},
            format="json",
        )
        self.assertEqual(choice.status_code, 201)
        listing = self.client.get(camera_url)
        self.assertEqual(len(listing.data), 1)
        self.assertEqual(listing.data[0]["choices"][0]["value"], "4mp")

        changed = self.client.patch(
            f"/api/v1/staff/catalog/specification-choices/{choice.data['id']}/",
            {"label": "4 Megapixel"},
            format="json",
        )
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(changed.data["label"], "4 Megapixel")

        type_change = self.client.patch(
            f"/api/v1/staff/catalog/specifications/{definition_id}/",
            {"data_type": "text"},
            format="json",
        )
        self.assertEqual(type_change.status_code, 400)
        self.assertIn("data_type", type_change.data["error"]["fields"])

        non_choice = SpecificationDefinition.objects.create(
            category=self.storage,
            key="capacity",
            label="Capacity",
            data_type=SpecificationDefinition.DataType.DECIMAL,
        )
        invalid_choice = self.client.post(
            f"/api/v1/staff/catalog/specifications/{non_choice.id}/choices/",
            {"value": "2tb", "label": "2 TB"},
            format="json",
        )
        self.assertEqual(invalid_choice.status_code, 400)

    def test_specification_management_requires_staff(self):
        definition = SpecificationDefinition.objects.create(
            category=self.cameras,
            key="sensor",
            label="Sensor",
            data_type=SpecificationDefinition.DataType.TEXT,
        )
        routes = (
            ("post", f"/api/v1/staff/catalog/categories/{self.cameras.id}/specifications/", {
                "key": "lens", "label": "Lens", "data_type": "text",
            }),
            ("patch", f"/api/v1/staff/catalog/specifications/{definition.id}/", {"label": "Changed"}),
            ("post", f"/api/v1/staff/catalog/specifications/{definition.id}/choices/", {
                "value": "one", "label": "One",
            }),
        )
        for user, expected in ((None, 401), (self.customer, 403)):
            for method, url, data in routes:
                with self.subTest(user=user, method=method, url=url):
                    self.client.credentials()
                    if user:
                        self.authorize(user)
                    response = getattr(self.client, method)(url, data, format="json")
                    self.assertEqual(response.status_code, expected)
        definition.refresh_from_db()
        self.assertEqual(definition.label, "Sensor")
        self.assertEqual(SpecificationDefinition.objects.count(), 1)
        self.assertEqual(SpecificationChoice.objects.count(), 0)

    def test_products_accept_only_typed_values_from_their_category(self):
        resolution, capacity = self.create_required_definitions()
        self.authorize(self.staff)
        collection = "/api/v1/staff/catalog/products/"

        wrong_category = self.client.post(
            collection,
            self.product_payload(specifications=[{"definition": capacity.id, "value": "2.0"}]),
            format="json",
        )
        self.assertEqual(wrong_category.status_code, 400)
        self.assertIn("specifications", wrong_category.data["error"]["fields"])

        wrong_type = self.client.post(
            collection,
            self.product_payload(specifications=[{"definition": resolution.id, "value": 4}]),
            format="json",
        )
        self.assertEqual(wrong_type.status_code, 400)

        duplicate = self.client.post(
            collection,
            self.product_payload(specifications=[
                {"definition": resolution.id, "value": "4mp"},
                {"definition": resolution.id, "value": "4mp"},
            ]),
            format="json",
        )
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(Product.objects.count(), 0)

        camera = self.client.post(
            collection,
            self.product_payload(specifications=[{"definition": resolution.id, "value": "4mp"}]),
            format="json",
        )
        self.assertEqual(camera.status_code, 201)
        self.assertEqual(camera.data["specifications"][0]["value"], "4mp")

        drive = self.client.post(
            collection,
            self.product_payload(
                category=self.storage,
                sku="HDD-2TB",
                slug="surveillance-drive-2tb",
                specifications=[{"definition": capacity.id, "value": "2.0"}],
            ),
            format="json",
        )
        self.assertEqual(drive.status_code, 201)
        self.assertEqual(drive.data["specifications"][0]["value"], "2.0000")
        self.assertEqual(ProductSpecificationValue.objects.count(), 2)

    def test_publication_requires_complete_product_and_is_atomic(self):
        resolution, _ = self.create_required_definitions()
        self.authorize(self.staff)
        created = self.client.post("/api/v1/staff/catalog/products/", self.product_payload(), format="json")
        product = Product.objects.get(pk=created.data["id"])
        detail = f"/api/v1/staff/catalog/products/{product.id}/"

        rejected = self.client.patch(detail, {"is_published": True}, format="json")
        self.assertEqual(rejected.status_code, 400)
        self.assertIn("is_published", rejected.data["error"]["fields"])
        product.refresh_from_db()
        self.assertFalse(product.is_published)
        self.assertEqual(AuditEvent.objects.count(), 0)

        published = self.client.patch(detail, {
            "specifications": [{"definition": resolution.id, "value": "4mp"}],
            "is_published": True,
        }, format="json")
        self.assertEqual(published.status_code, 200)
        self.assertTrue(published.data["is_published"])
        self.assertEqual(published.data["stock_quantity"], 0)
        event = AuditEvent.objects.get()
        self.assertEqual(event.actor, self.staff)
        self.assertEqual(event.action, "PRODUCT_PUBLISHED")

        invalid_edit = self.client.patch(detail, {"specifications": []}, format="json")
        self.assertEqual(invalid_edit.status_code, 400)
        product.refresh_from_db()
        self.assertTrue(product.is_published)
        self.assertEqual(product.specification_values.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), 1)

    def test_public_endpoints_hide_drafts_and_keep_published_zero_stock_visible(self):
        resolution, _ = self.create_required_definitions()
        hidden = Product.objects.create(
            brand=self.brand,
            category=self.cameras,
            sku="DRAFT-001",
            slug="draft-001",
            name="Hidden Draft",
            short_description="Draft short description",
            full_description="Draft full description",
            regular_price=Decimal("100.00"),
        )
        self.authorize(self.staff)
        created = self.client.post(
            "/api/v1/staff/catalog/products/",
            self.product_payload(
                sku="PUBLIC-001",
                slug="public-001",
                specifications=[{"definition": resolution.id, "value": "4mp"}],
            ),
            format="json",
        )
        product_id = created.data["id"]
        self.client.patch(
            f"/api/v1/staff/catalog/products/{product_id}/",
            {"is_published": True},
            format="json",
        )

        self.client.credentials()
        listing = self.client.get("/api/v1/catalog/products/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data["count"], 1)
        self.assertEqual(listing.data["results"][0]["slug"], "public-001")
        self.assertEqual(listing.data["results"][0]["stock_quantity"], 0)
        self.assertFalse(listing.data["results"][0]["is_in_stock"])
        self.assertEqual(self.client.get(f"/api/v1/catalog/products/{hidden.slug}/").status_code, 404)

        public_detail = self.client.get("/api/v1/catalog/products/public-001/")
        self.assertEqual(public_detail.status_code, 200)
        self.assertEqual(public_detail.data["specifications"][0]["key"], "resolution")
        self.assertEqual(public_detail.data["specifications"][0]["display_value"], "4 MP")

        self.authorize(self.staff)
        unpublished = self.client.patch(
            f"/api/v1/staff/catalog/products/{product_id}/",
            {"is_published": False},
            format="json",
        )
        self.assertEqual(unpublished.status_code, 200)
        self.assertEqual(
            list(AuditEvent.objects.order_by("created_at").values_list("action", flat=True)),
            ["PRODUCT_PUBLISHED", "PRODUCT_UNPUBLISHED"],
        )
        self.client.credentials()
        self.assertEqual(self.client.get("/api/v1/catalog/products/").data["count"], 0)
        self.assertEqual(self.client.get("/api/v1/catalog/products/public-001/").status_code, 404)

    def test_inactive_taxonomy_cannot_be_published(self):
        inactive_brand = Brand.objects.create(name="Inactive", slug="inactive", is_active=False)
        product = Product.objects.create(
            brand=inactive_brand,
            category=self.cameras,
            sku="INACTIVE-001",
            slug="inactive-001",
            name="Inactive Brand Product",
            short_description="Short description",
            full_description="Full description",
            regular_price=Decimal("100.00"),
        )
        self.authorize(self.staff)
        response = self.client.patch(
            f"/api/v1/staff/catalog/products/{product.id}/",
            {"is_published": True},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        product.refresh_from_db()
        self.assertFalse(product.is_published)
