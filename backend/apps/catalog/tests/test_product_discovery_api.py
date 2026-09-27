from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from apps.catalog.models import (
    Brand, Category, Product, ProductSpecificationValue, SpecificationChoice, SpecificationDefinition,
)


class PublicProductDiscoveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hikvision = Brand.objects.create(name="Hikvision", slug="hikvision")
        cls.dahua = Brand.objects.create(name="Dahua", slug="dahua")
        cls.inactive_brand = Brand.objects.create(name="Inactive", slug="inactive", is_active=False)
        cls.cameras = Category.objects.create(name="Cameras", slug="cameras")
        cls.storage = Category.objects.create(name="Storage", slug="storage")
        cls.inactive_category = Category.objects.create(name="Inactive", slug="inactive", is_active=False)
        cls.resolution = SpecificationDefinition.objects.create(
            category=cls.cameras, key="resolution", label="Resolution",
            data_type="choice", is_filterable=True, sort_order=0,
        )
        cls.two_mp = SpecificationChoice.objects.create(definition=cls.resolution, value="2mp", label="2 MP")
        cls.four_mp = SpecificationChoice.objects.create(definition=cls.resolution, value="4mp", label="4 MP")
        cls.retired = SpecificationChoice.objects.create(
            definition=cls.resolution, value="retired", label="Retired", is_active=False,
        )
        cls.ir_distance = SpecificationDefinition.objects.create(
            category=cls.cameras, key="ir_distance", label="IR Distance",
            data_type="decimal", unit="m", is_filterable=True, sort_order=1,
        )
        cls.outdoor = SpecificationDefinition.objects.create(
            category=cls.cameras, key="outdoor", label="Outdoor", data_type="boolean", is_filterable=True,
            sort_order=2,
        )
        cls.capacity = SpecificationDefinition.objects.create(
            category=cls.storage, key="capacity", label="Capacity", data_type="integer", unit="TB",
            is_filterable=True,
        )
        cls.secret = SpecificationDefinition.objects.create(
            category=cls.cameras, key="secret", label="Secret", data_type="choice", is_filterable=False,
        )
        SpecificationDefinition.objects.create(
            category=cls.cameras, key="unused", label="Unused", data_type="integer", is_filterable=True,
        )

        cls.exact = cls.product("DS-2CE", "Exact model camera", cls.hikvision, cls.cameras, "10000.00", "9000.00", 5)
        cls.prefix = cls.product("DS-2CE-PLUS", "Another camera", cls.hikvision, cls.cameras, "14000.00", None, 0)
        cls.name_match = cls.product("CAM-003", "DS-2CE name match", cls.dahua, cls.cameras, "7000.00", None, 2)
        cls.drive = cls.product("HDD-2TB", "Surveillance storage", cls.dahua, cls.storage, "6000.00", None, 0)
        cls.draft = cls.product("DRAFT-DS-2CE", "Draft model", cls.hikvision, cls.cameras,
                                "100.00", None, 2, published=False)
        cls.inactive = cls.product("INACTIVE-DS-2CE", "Inactive model", cls.inactive_brand,
                                   cls.cameras, "100.00", None, 2)
        cls.inactive_category_product = cls.product("OLD-DS-2CE", "Old model", cls.hikvision,
                                                    cls.inactive_category, "100.00", None, 2)
        for product, choice, distance, outdoor in (
            (cls.exact, cls.two_mp, "20.0000", True),
            (cls.prefix, cls.four_mp, "50.0000", False),
            (cls.name_match, cls.two_mp, "30.0000", True),
        ):
            ProductSpecificationValue.objects.create(product=product, definition=cls.resolution, choice=choice)
            ProductSpecificationValue.objects.create(
                product=product, definition=cls.ir_distance, decimal_value=distance,
            )
            ProductSpecificationValue.objects.create(
                product=product, definition=cls.outdoor, boolean_value=outdoor,
            )
        ProductSpecificationValue.objects.create(product=cls.drive, definition=cls.capacity, integer_value=2)

    @classmethod
    def product(cls, sku, name, brand, category, price, sale, stock, *, published=True):
        return Product.objects.create(
            brand=brand, category=category, sku=sku, slug=sku.lower(), name=name,
            short_description="Test product", full_description="Test product details",
            regular_price=price, sale_price=sale, stock_quantity=stock, is_published=published,
        )

    def setUp(self):
        self.client = APIClient()
        self.url = "/api/v1/catalog/products/"

    def slugs(self, params=None):
        response = self.client.get(self.url, params or {})
        self.assertEqual(response.status_code, 200, response.data)
        return [item["slug"] for item in response.data["results"]]

    def test_search_model_and_name_with_relevance_order_and_public_scope(self):
        self.assertEqual(self.slugs({"q": "ds-2ce"}), ["ds-2ce", "ds-2ce-plus", "cam-003"])
        self.assertEqual(self.slugs({"q": "camera"}), ["ds-2ce-plus", "ds-2ce"])
        self.assertEqual(self.slugs({"q": "hdd-2"}), ["hdd-2tb"])
        self.assertEqual(self.slugs({"q": "draft"}), [])
        self.assertEqual(self.slugs({"q": "inactive"}), [])

    def test_basic_filters_use_selling_price_and_keep_sold_out_visible(self):
        self.assertEqual(self.slugs({"category": "cameras", "brand": "hikvision"}),
                         ["ds-2ce-plus", "ds-2ce"])
        self.assertEqual(self.slugs({"min_price": "8000", "max_price": "12000"}), ["ds-2ce"])
        self.assertEqual(self.slugs({"availability": "out_of_stock", "sort": "price_asc"}),
                         ["hdd-2tb", "ds-2ce-plus"])
        self.assertEqual(self.slugs({"availability": "in_stock", "sort": "price_desc"}),
                         ["ds-2ce", "cam-003"])
        self.assertEqual(self.slugs({"category": "missing"}), [])

    def test_typed_specification_filters_combine_without_duplicate_products(self):
        self.assertEqual(self.slugs({"category": "cameras", "spec_resolution": "2mp",
                                     "spec_ir_distance_min": "20", "spec_ir_distance_max": "25",
                                     "spec_outdoor": "true"}), ["ds-2ce"])
        self.assertEqual(self.slugs({"category": "cameras", "spec_outdoor": "false"}), ["ds-2ce-plus"])
        self.assertEqual(self.slugs({"category": "storage", "spec_capacity_min": "2",
                                     "spec_capacity_max": "3"}), ["hdd-2tb"])
        self.assertEqual(self.slugs({"category": "storage", "spec_capacity_max": "1"}), [])

    def test_rejects_invalid_or_cross_category_filters(self):
        cases = (
            ({"min_price": "12", "max_price": "10"}, "max_price"),
            ({"min_price": "-1"}, "min_price"),
            ({"availability": "yes"}, "availability"),
            ({"sort": "newest"}, "sort"),
            ({"spec_resolution": "2mp"}, "category"),
            ({"category": "storage", "spec_resolution": "2mp"}, "spec_resolution"),
            ({"category": "cameras", "spec_secret": "anything"}, "spec_secret"),
            ({"category": "cameras", "spec_resolution": "retired"}, "spec_resolution"),
            ({"category": "cameras", "spec_resolution_min": "2"}, "spec_resolution_min"),
            ({"category": "cameras", "spec_outdoor": "maybe"}, "spec_outdoor"),
            ({"category": "cameras", "spec_ir_distance_min": "50", "spec_ir_distance_max": "20"},
             "spec_ir_distance_max"),
            ({"category": "storage", "spec_capacity_min": "2.5"}, "spec_capacity_min"),
            ({"mystery": "value"}, "mystery"),
        )
        for params, field in cases:
            with self.subTest(params=params):
                response = self.client.get(self.url, params)
                self.assertEqual(response.status_code, 400, response.data)
                self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
                self.assertIn(field, response.data["error"]["fields"])

    def test_pagination_and_stable_price_ties(self):
        self.product("CAM-004", "Another cheap camera", self.dahua, self.cameras, "7000.00", None, 1)
        from apps.catalog.api.views import CatalogPagination
        with patch.object(CatalogPagination, "page_size", 2):
            first = self.client.get(self.url, {"sort": "price_asc"})
            second = self.client.get(self.url, {"sort": "price_asc", "page": 2})
            self.assertEqual(first.data["count"], 5)
            self.assertIsNotNone(first.data["next"])
            self.assertEqual([item["slug"] for item in first.data["results"]], ["hdd-2tb", "cam-003"])
            self.assertEqual([item["slug"] for item in second.data["results"]], ["cam-004", "ds-2ce"])

    def test_filter_metadata_is_scoped_to_public_products_and_category(self):
        response = self.client.get("/api/v1/catalog/filters/", {"category": "cameras"})
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertEqual([item["value"] for item in data["brand"]], ["dahua", "hikvision"])
        self.assertEqual(data["price"], {"min": "7000.00", "max": "14000.00"})
        self.assertEqual([item["key"] for item in data["specifications"]],
                         ["resolution", "ir_distance", "outdoor"])
        self.assertEqual([item["value"] for item in data["specifications"][0]["options"]], ["2mp", "4mp"])
        self.assertEqual(data["specifications"][1]["min"], "20.0000")
        self.assertEqual(data["specifications"][1]["max"], "50.0000")
        self.assertEqual([item["value"] for item in data["specifications"][2]["options"]], [True, False])
        storage = self.client.get("/api/v1/catalog/filters/", {"category": "storage"}).data
        self.assertEqual([item["key"] for item in storage["specifications"]], ["capacity"])
        brand_scope = self.client.get("/api/v1/catalog/filters/", {"brand": "hikvision"}).data
        self.assertEqual([item["value"] for item in brand_scope["category"]], ["cameras"])
        self.assertEqual([item["value"] for item in brand_scope["brand"]], ["dahua", "hikvision"])
        all_filters = self.client.get("/api/v1/catalog/filters/").data
        self.assertEqual(all_filters["specifications"], [])
        self.assertEqual([item["value"] for item in all_filters["category"]], ["cameras", "storage"])
        empty = self.client.get("/api/v1/catalog/filters/", {"category": "missing"}).data
        self.assertEqual(empty["price"], {"min": None, "max": None})
        self.assertEqual(empty["specifications"], [])

    def test_metadata_rejects_unknown_inputs_and_list_prefetch_is_bounded(self):
        response = self.client.get("/api/v1/catalog/filters/", {"spec_resolution": "2mp"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("spec_resolution", response.data["error"]["fields"])
        duplicate = self.client.get(self.url + "?brand=hikvision&brand=dahua")
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("brand", duplicate.data["error"]["fields"])
        with self.assertNumQueries(3):
            self.client.get(self.url)
