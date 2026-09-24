from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.catalog.models import Brand, Category


class TaxonomyApiTests(TestCase):
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

    def authorize(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")

    def test_public_lists_and_details_hide_inactive_entries_even_with_query_override(self):
        for model, route in ((Brand, "brands"), (Category, "categories")):
            with self.subTest(route=route):
                active = model.objects.create(name="Visible", slug="visible")
                model.objects.create(name="Hidden", slug="hidden", is_active=False)
                response = self.client.get(f"/api/v1/catalog/{route}/?is_active=false&include_inactive=true")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["count"], 1)
                self.assertEqual(response.data["results"][0]["id"], active.id)
                self.assertEqual(self.client.get(f"/api/v1/catalog/{route}/visible/").status_code, 200)
                hidden = self.client.get(f"/api/v1/catalog/{route}/hidden/")
                self.assertEqual(hidden.status_code, 404)
                self.assertEqual(hidden.data["error"]["code"], "NOT_FOUND")

    def test_all_staff_routes_reject_visitors_and_customers_without_mutation(self):
        for model, route in ((Brand, "brands"), (Category, "categories")):
            entry = model.objects.create(name="Existing", slug="existing")
            collection = f"/api/v1/staff/catalog/{route}/"
            for user, expected in ((None, 401), (self.customer, 403)):
                with self.subTest(route=route, expected=expected):
                    self.client.credentials()
                    if user:
                        self.authorize(user)
                    self.assertEqual(self.client.get(collection).status_code, expected)
                    self.assertEqual(self.client.post(collection, {"name": "New", "slug": "new"}).status_code, expected)
                    response = self.client.patch(f"{collection}{entry.id}/", {"is_active": False}, format="json")
                    self.assertEqual(response.status_code, expected)
                    self.assertEqual(response.data["error"]["code"],
                                     "AUTHENTICATION_REQUIRED" if expected == 401 else "PERMISSION_DENIED")
                    entry.refresh_from_db()
                    self.assertTrue(entry.is_active)
                    self.assertEqual(model.objects.count(), 1)

    def test_staff_create_edit_deactivate_and_reactivate(self):
        self.authorize(self.staff)
        for model, route in ((Brand, "brands"), (Category, "categories")):
            with self.subTest(route=route):
                collection = f"/api/v1/staff/catalog/{route}/"
                created = self.client.post(collection, {"name": "Sample", "slug": "sample"}, format="json")
                self.assertEqual(created.status_code, 201)
                detail = f"{collection}{created.data['id']}/"
                edited = self.client.patch(detail, {"name": "Renamed", "description": "Updated", "sort_order": 2},
                                           format="json")
                self.assertEqual(edited.status_code, 200)
                self.assertEqual(edited.data["slug"], "sample")
                self.assertEqual(edited.data["description"], "Updated")
                self.assertEqual(self.client.patch(detail, {"is_active": False}, format="json").status_code, 200)
                self.assertEqual(self.client.get(f"/api/v1/catalog/{route}/").data["count"], 0)
                self.assertEqual(self.client.get(f"/api/v1/catalog/{route}/sample/").status_code, 404)
                staff_list = self.client.get(collection)
                self.assertEqual(staff_list.data["count"], 1)
                self.assertFalse(staff_list.data["results"][0]["is_active"])
                self.assertEqual(model.objects.count(), 1)
                self.assertEqual(self.client.patch(detail, {"is_active": True}, format="json").status_code, 200)
                self.assertEqual(self.client.get(f"/api/v1/catalog/{route}/sample/").status_code, 200)

    def test_validation_and_unique_fields_on_create_and_update(self):
        self.authorize(self.staff)
        for model, route in ((Brand, "brands"), (Category, "categories")):
            model.objects.create(name="Existing", slug="existing", is_active=False)
            other = model.objects.create(name="Other", slug="other")
            collection = f"/api/v1/staff/catalog/{route}/"
            for payload, field in (({"name": "Existing", "slug": "unique"}, "name"),
                                   ({"name": "Unique", "slug": "existing"}, "slug"),
                                   ({"name": "", "slug": "unique"}, "name"),
                                   ({"name": "Unique", "slug": "bad slug"}, "slug"),
                                   ({"name": "Unique", "slug": "unique", "sort_order": -1}, "sort_order")):
                with self.subTest(route=route, payload=payload):
                    response = self.client.post(collection, payload, format="json")
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
                    self.assertIn(field, response.data["error"]["fields"])
            response = self.client.patch(f"{collection}{other.id}/", {"slug": "existing"}, format="json")
            self.assertEqual(response.status_code, 400)
            other.refresh_from_db()
            self.assertEqual(other.slug, "other")

    def test_public_writes_and_hard_deletes_are_unavailable(self):
        self.authorize(self.staff)
        for model, route in ((Brand, "brands"), (Category, "categories")):
            entry = model.objects.create(name="Existing", slug="existing")
            self.assertEqual(self.client.post(f"/api/v1/catalog/{route}/", {}).status_code, 405)
            self.assertEqual(self.client.patch(f"/api/v1/catalog/{route}/existing/", {}).status_code, 405)
            self.assertEqual(self.client.delete(f"/api/v1/staff/catalog/{route}/{entry.id}/").status_code, 405)
            self.assertTrue(model.objects.filter(pk=entry.pk).exists())

    def test_lists_are_paginated_and_ordered(self):
        self.authorize(self.staff)
        for model, route in ((Brand, "brands"), (Category, "categories")):
            model.objects.bulk_create([
                model(name=f"Entry {i:02}", slug=f"entry-{i}", sort_order=i) for i in range(21)
            ])
            for prefix in ("catalog", "staff/catalog"):
                with self.subTest(route=route, prefix=prefix):
                    response = self.client.get(f"/api/v1/{prefix}/{route}/")
                    self.assertEqual(response.data["count"], 21)
                    self.assertEqual(len(response.data["results"]), 20)
                    self.assertEqual(response.data["results"][0]["name"], "Entry 00")
                    self.assertIsNotNone(response.data["next"])
                    second = self.client.get(f"/api/v1/{prefix}/{route}/?page=2")
                    self.assertEqual(second.data["results"][0]["name"], "Entry 20")

    def test_revoked_staff_role_is_checked_for_existing_token(self):
        self.authorize(self.staff)
        get_user_model().objects.filter(pk=self.staff.pk).update(is_staff=False)
        for route in ("brands", "categories"):
            self.assertEqual(self.client.post(f"/api/v1/staff/catalog/{route}/", {
                "name": "Forbidden", "slug": "forbidden",
            }, format="json").status_code, 403)
        self.assertEqual(Brand.objects.count(), 0)
        self.assertEqual(Category.objects.count(), 0)
