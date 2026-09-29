import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import URLResolver, get_resolver, resolve, reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.services import issue_tokens
from apps.orders.models import Order, OrderItem


def create_order(*, user=None, **changes):
    """Use saved checkout data without depending on live pricing configuration."""
    data = {
        "reference": f"OC-{uuid.uuid4().hex[:16].upper()}",
        "user": user,
        "customer_name": "Saved checkout name",
        "customer_email": "checkout@example.com",
        "customer_phone": "03001111111",
        "delivery_address_line1": "10 Test Street",
        "delivery_address_line2": "Saved floor",
        "delivery_city": "Lahore",
        "delivery_province": "Punjab",
        "delivery_postal_code": "54000",
        "delivery_country": "PK",
        "subtotal": "1000.00",
        "tax_total": "150.00",
        "shipping_fee": "100.00",
        "shipping_tax_amount": "0.00",
        "grand_total": "1250.00",
        "tax_rate_percent": "15.00",
        "shipping_taxable": False,
        "idempotency_key": uuid.uuid4(),
        "request_fingerprint": "a" * 64,
    }
    data.update(changes)
    return Order.objects.create(**data)


class CustomerAccountApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # The historical guest checkout predates the account and uses its email.
        cls.guest_order = create_order(customer_email="buyer@example.com")
        cls.customer = get_user_model().objects.create_user(
            email="buyer@example.com", password="a-strong-test-password",
            full_name="Current account name", phone="03002222222",
        )
        cls.other_customer = get_user_model().objects.create_user(
            email="other@example.com", password="a-strong-test-password", full_name="Other buyer",
        )
        cls.staff = get_user_model().objects.create_user(
            email="staff@example.com", password="a-strong-test-password", full_name="Staff", is_staff=True,
        )
        cls.own_order = create_order(
            user=cls.customer, placed_at=timezone.now() - timedelta(days=3),
            status=Order.Status.SHIPPED, payment_status=Order.PaymentStatus.UNCOLLECTED,
            courier_name="Test courier", tracking_number="TEST-123",
            tracking_url="https://courier.example/track/TEST-123",
        )
        # Matching checkout email alone must never grant account ownership.
        cls.other_order = create_order(user=cls.other_customer, customer_email=cls.customer.email)
        cls.own_item = OrderItem.objects.create(
            order=cls.own_order, product=None, product_name="Saved camera name", sku="SAVED-CAMERA-01",
            quantity=2, unit_price="500.00", line_subtotal="1000.00", tax_amount="150.00",
        )

    def setUp(self):
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)
        self.access, self.refresh = issue_tokens(self.customer)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access}")

    def detail_url(self, order):
        return f"/api/v1/account/orders/{order.public_id}/"

    def account_requests(self, client):
        return (
            client.get("/api/v1/account/profile/"),
            client.patch("/api/v1/account/profile/", {"full_name": "Unauthorized change"}, format="json"),
            client.get("/api/v1/account/orders/"),
            client.get(self.detail_url(self.own_order)),
        )

    def test_profile_get_returns_only_the_signed_in_customer(self):
        response = self.client.get("/api/v1/account/profile/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "id": self.customer.pk,
            "email": self.customer.email,
            "full_name": self.customer.full_name,
            "phone": self.customer.phone,
            "is_staff": False,
        })

    def test_profile_partial_update_uses_existing_bearer_auth_and_preserves_credentials(self):
        original_password = self.customer.password
        response = self.client.patch(
            "/api/v1/account/profile/", {"full_name": "Updated buyer"}, format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["full_name"], "Updated buyer")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.full_name, "Updated buyer")
        self.assertEqual(self.customer.phone, "03002222222")
        self.assertEqual(self.customer.email, "buyer@example.com")
        self.assertEqual(self.customer.password, original_password)
        self.assertFalse(self.customer.is_staff)
        self.assertTrue(self.customer.is_active)
        # Ordinary profile edits must not revoke this already-issued JWT.
        self.assertEqual(self.client.get("/api/v1/account/profile/").status_code, 200)
        self.assertEqual(self.client.get(self.detail_url(self.own_order)).status_code, 200)

    def test_profile_phone_can_be_cleared_without_changing_name(self):
        response = self.client.patch("/api/v1/account/profile/", {"phone": ""}, format="json")

        self.assertEqual(response.status_code, 200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.phone, "")
        self.assertEqual(self.customer.full_name, "Current account name")

    def test_profile_rejects_blank_name_and_oversized_permitted_fields(self):
        for field, value in (
            ("full_name", ""), ("full_name", "   "), ("full_name", "x" * 256), ("phone", "x" * 31),
        ):
            with self.subTest(field=field, value=value):
                response = self.client.patch("/api/v1/account/profile/", {field: value}, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")
                self.assertIn(field, response.json()["error"]["fields"])

        self.customer.refresh_from_db()
        self.assertEqual(self.customer.full_name, "Current account name")
        self.assertEqual(self.customer.phone, "03002222222")

    def test_profile_rejects_protected_and_unknown_fields_without_partial_writes(self):
        original = get_user_model().objects.filter(pk=self.customer.pk).values().get()
        forbidden = {
            "email": "changed@example.com",
            "password": "another-strong-test-password",
            "id": self.other_customer.pk,
            "is_staff": True,
            "is_superuser": True,
            "is_active": False,
            "date_joined": "2000-01-01T00:00:00Z",
            "unknown_field": "unsupported",
        }

        for field, value in forbidden.items():
            with self.subTest(field=field):
                response = self.client.patch(
                    "/api/v1/account/profile/", {"full_name": "Must not save", field: value}, format="json",
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")
                self.assertIn(field, response.json()["error"]["fields"])
                self.assertEqual(get_user_model().objects.filter(pk=self.customer.pk).values().get(), original)

    def test_profile_edits_leave_order_and_item_snapshots_and_guest_ownership_unchanged(self):
        order_snapshots = list(Order.objects.order_by("id").values())
        item_snapshots = list(OrderItem.objects.order_by("id").values())

        response = self.client.patch(
            "/api/v1/account/profile/", {"full_name": "New account name", "phone": "03003333333"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(Order.objects.order_by("id").values()), order_snapshots)
        self.assertEqual(list(OrderItem.objects.order_by("id").values()), item_snapshots)
        self.guest_order.refresh_from_db()
        self.assertIsNone(self.guest_order.user_id)
        detail = self.client.get(self.detail_url(self.own_order))
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["customer_name"], "Saved checkout name")
        self.assertEqual(detail.json()["customer_phone"], "03001111111")

    def test_anonymous_requests_cannot_read_or_edit_account_data(self):
        client = APIClient(enforce_csrf_checks=True)

        for response in self.account_requests(client):
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json()["error"]["code"], "AUTHENTICATION_REQUIRED")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.full_name, "Current account name")

    def test_refresh_cookie_alone_does_not_authorize_account_endpoints(self):
        client = APIClient(enforce_csrf_checks=True)
        client.cookies[settings.AUTH_REFRESH_COOKIE_NAME] = self.refresh

        for response in self.account_requests(client):
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json()["error"]["code"], "AUTHENTICATION_REQUIRED")

    def test_staff_cannot_use_customer_profile_or_order_endpoints(self):
        staff_access, _ = issue_tokens(self.staff)
        client = APIClient(enforce_csrf_checks=True)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {staff_access}")

        for response in self.account_requests(client):
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()["error"]["code"], "PERMISSION_DENIED")

    def test_disabled_customer_cannot_read_orders_with_an_existing_access_token(self):
        self.customer.is_active = False
        self.customer.save(update_fields=["is_active"])

        for path in ("/api/v1/account/orders/", self.detail_url(self.own_order)):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json()["error"]["code"], "AUTHENTICATION_REQUIRED")

    def test_history_contains_only_explicitly_owned_orders_even_when_emails_match(self):
        response = self.client.get("/api/v1/account/orders/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual([order["public_id"] for order in data["results"]], [str(self.own_order.public_id)])
        self.assertEqual(data["results"][0]["reference"], self.own_order.reference)
        self.assertEqual(data["results"][0]["status"], Order.Status.SHIPPED)
        self.assertEqual(data["results"][0]["payment_status"], Order.PaymentStatus.UNCOLLECTED)
        self.assertEqual(data["results"][0]["grand_total"], "1250.00")
        for field in ("id", "user", "user_id", "idempotency_key", "request_fingerprint", "guest_link_nonce"):
            self.assertNotIn(field, data["results"][0])
        self.assertIsNone(data["next"])
        self.assertIsNone(data["previous"])

    def test_history_is_paginated_newest_first_with_a_stable_tie_breaker(self):
        placed_at = timezone.now()
        newest = [create_order(user=self.customer, placed_at=placed_at) for _ in range(20)]

        first = self.client.get("/api/v1/account/orders/")
        self.assertEqual(first.status_code, 200)
        first_data = first.json()
        self.assertEqual(first_data["count"], 21)
        self.assertEqual(
            [order["public_id"] for order in first_data["results"]],
            [str(order.public_id) for order in reversed(newest)],
        )
        self.assertIsNotNone(first_data["next"])
        self.assertIsNone(first_data["previous"])

        second = self.client.get("/api/v1/account/orders/?page=2")
        self.assertEqual(second.status_code, 200)
        second_data = second.json()
        self.assertEqual([order["public_id"] for order in second_data["results"]], [str(self.own_order.public_id)])
        self.assertIsNone(second_data["next"])
        self.assertIsNotNone(second_data["previous"])

    def test_customer_with_no_owned_orders_receives_empty_paginated_history(self):
        access, _ = issue_tokens(self.other_customer)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        self.other_order.user = None
        self.other_order.save(update_fields=["user"])

        response = self.client.get("/api/v1/account/orders/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"count": 0, "next": None, "previous": None, "results": []})

    def test_owned_order_detail_returns_saved_contact_address_items_totals_and_courier(self):
        response = self.client.get(self.detail_url(self.own_order))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        expected = {
            "public_id": str(self.own_order.public_id),
            "reference": self.own_order.reference,
            "customer_name": "Saved checkout name",
            "customer_email": "checkout@example.com",
            "customer_phone": "03001111111",
            "delivery_address_line1": "10 Test Street",
            "delivery_address_line2": "Saved floor",
            "delivery_city": "Lahore",
            "delivery_province": "Punjab",
            "delivery_postal_code": "54000",
            "delivery_country": "PK",
            "subtotal": "1000.00",
            "tax_total": "150.00",
            "shipping_fee": "100.00",
            "shipping_tax_amount": "0.00",
            "grand_total": "1250.00",
            "tax_rate_percent": "15.00",
            "shipping_taxable": False,
            "status": Order.Status.SHIPPED,
            "payment_method": Order.PaymentMethod.COD,
            "payment_status": Order.PaymentStatus.UNCOLLECTED,
            "courier_name": "Test courier",
            "tracking_number": "TEST-123",
            "tracking_url": "https://courier.example/track/TEST-123",
        }
        for field, value in expected.items():
            with self.subTest(field=field):
                self.assertEqual(data[field], value)
        self.assertIn("placed_at", data)
        self.assertEqual(data["items"], [{
            "product_name": "Saved camera name", "sku": "SAVED-CAMERA-01", "quantity": 2,
            "unit_price": "500.00", "line_subtotal": "1000.00", "tax_amount": "150.00",
        }])
        for field in (
            "id", "user", "user_id", "idempotency_key", "request_fingerprint", "guest_link_nonce",
            "guest_tracking_url",
        ):
            self.assertNotIn(field, data)

    def test_customer_order_patch_and_delete_are_unsupported_and_leave_snapshots_unchanged(self):
        order_snapshots = list(Order.objects.order_by("id").values())
        item_snapshots = list(OrderItem.objects.order_by("id").values())

        for path in ("/api/v1/account/orders/", self.detail_url(self.own_order)):
            with self.subTest(path=path):
                patch = self.client.patch(path, {
                    "status": Order.Status.CANCELLED, "customer_name": "Changed checkout", "grand_total": "1.00",
                }, format="json")
                self.assertEqual(patch.status_code, 405)
                self.assertEqual(self.client.delete(path).status_code, 405)

        self.assertEqual(list(Order.objects.order_by("id").values()), order_snapshots)
        self.assertEqual(list(OrderItem.objects.order_by("id").values()), item_snapshots)

    def test_other_customer_guest_and_unknown_order_details_are_indistinguishable_not_found(self):
        responses = [
            self.client.get(self.detail_url(self.other_order)),
            self.client.get(self.detail_url(self.guest_order)),
            self.client.get(f"/api/v1/account/orders/{uuid.uuid4()}/"),
        ]

        for response in responses:
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json()["error"]["code"], "NOT_FOUND")
        self.assertEqual(responses[0].json(), responses[1].json())
        self.assertEqual(responses[0].json(), responses[2].json())

    def test_registration_never_claims_historical_guest_orders_by_email(self):
        guest = create_order(customer_email="new-customer@example.com")
        client = APIClient(enforce_csrf_checks=True)
        csrf_token = client.get("/api/v1/auth/csrf/").json()["csrfToken"]

        registration = client.post(
            "/api/v1/auth/register/", {
                "email": guest.customer_email, "full_name": "New customer", "password": "a-strong-test-password",
            }, format="json", HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(registration.status_code, 201)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {registration.json()['access']}")
        history = client.get("/api/v1/account/orders/")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json()["count"], 0)
        self.assertEqual(client.get(self.detail_url(guest)).status_code, 404)
        guest.refresh_from_db()
        self.assertIsNone(guest.user_id)

    def test_existing_profile_route_and_name_are_reused_once(self):
        def named_routes(patterns, prefix=""):
            for pattern in patterns:
                route = f"{prefix}{pattern.pattern}"
                if isinstance(pattern, URLResolver):
                    yield from named_routes(pattern.url_patterns, route)
                else:
                    yield route, pattern.name

        routes = list(named_routes(get_resolver().url_patterns))
        self.assertEqual([route for route, name in routes if name == "account-profile"], ["api/v1/account/profile/"])
        self.assertEqual(sum(route == "api/v1/account/profile/" for route, _ in routes), 1)
        self.assertEqual(reverse("account-profile"), "/api/v1/account/profile/")
        self.assertEqual(resolve("/api/v1/account/profile/").url_name, "account-profile")
