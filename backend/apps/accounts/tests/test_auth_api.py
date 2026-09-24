from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import close_old_connections, connections
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.services import issue_tokens, rotate_refresh
from apps.core.exceptions import AuthenticationError


class AuthApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)
        self.csrf_token = self.client.get("/api/v1/auth/csrf/").json()["csrfToken"]

    def post(self, path, data=None):
        return self.client.post(path, data or {}, format="json", HTTP_X_CSRFTOKEN=self.csrf_token)

    def register(self, **changes):
        data = {
            "email": "BUYER@Example.com",
            "full_name": "Test Buyer",
            "phone": "03001234567",
            "password": "a-strong-test-password",
        }
        data.update(changes)
        return self.post("/api/v1/auth/register/", data)

    def test_registration_creates_customer_and_sets_scoped_httponly_cookie(self):
        response = self.register(is_staff=True, is_superuser=True)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["user"]["email"], "buyer@example.com")
        self.assertFalse(response.data["user"]["is_staff"])
        self.assertNotIn("refresh", response.data)
        self.assertNotIn("password", response.data["user"])
        user = get_user_model().objects.get(email="buyer@example.com")
        self.assertTrue(user.check_password("a-strong-test-password"))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        cookie = response.cookies[settings.AUTH_REFRESH_COOKIE_NAME]
        self.assertEqual(cookie["path"], "/api/v1/auth/")
        self.assertTrue(cookie["httponly"])
        self.assertTrue(cookie["secure"])
        self.assertEqual(cookie["samesite"], "Lax")

    def test_duplicate_email_and_weak_password_are_validation_errors(self):
        self.assertEqual(self.register().status_code, 201)
        duplicate = self.register(email="buyer@example.COM")
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(duplicate.data["error"]["code"], "VALIDATION_ERROR")
        self.assertIn("email", duplicate.data["error"]["fields"])
        weak = self.register(email="other@example.com", password="123")
        self.assertEqual(weak.status_code, 400)
        self.assertIn("password", weak.data["error"]["fields"])

    def test_login_rejects_wrong_password_and_inactive_user(self):
        user = get_user_model().objects.create_user(
            email="buyer@example.com", password="a-strong-test-password", full_name="Buyer"
        )
        wrong = self.post("/api/v1/auth/login/", {"email": user.email, "password": "wrong"})
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(wrong.data["error"]["code"], "AUTHENTICATION_REQUIRED")
        user.is_active = False
        user.save(update_fields=["is_active"])
        inactive = self.post(
            "/api/v1/auth/login/", {"email": user.email, "password": "a-strong-test-password"}
        )
        self.assertEqual(inactive.status_code, 401)
        self.assertEqual(inactive.data["error"]["message"], wrong.data["error"]["message"])

    def test_login_rate_limit_uses_stable_error_code(self):
        for attempt in range(10):
            self.assertEqual(
                self.client.post(
                    "/api/v1/auth/login/", {"email": "missing@example.com", "password": "wrong"}, format="json",
                    HTTP_X_CSRFTOKEN=self.csrf_token, HTTP_X_FORWARDED_FOR=f"192.0.2.{attempt + 1}",
                ).status_code,
                401,
            )
        limited = self.post("/api/v1/auth/login/", {"email": "missing@example.com", "password": "wrong"})
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.data["error"]["code"], "RATE_LIMITED")

    def test_csrf_is_required_on_cookie_setting_and_cookie_authenticated_posts(self):
        missing = self.client.post(
            "/api/v1/auth/register/",
            {"email": "buyer@example.com", "full_name": "Buyer", "password": "a-strong-test-password"},
            format="json",
        )
        self.assertEqual(missing.status_code, 403)
        self.assertEqual(missing.json()["error"]["code"], "PERMISSION_DENIED")
        self.assertEqual(self.register().status_code, 201)
        for path in ("/api/v1/auth/refresh/", "/api/v1/auth/logout/"):
            response = self.client.post(path, {}, format="json")
            self.assertEqual(response.status_code, 403)
        cross_site = self.client.post(
            "/api/v1/auth/refresh/", {}, format="json", HTTP_X_CSRFTOKEN=self.csrf_token,
            HTTP_ORIGIN="https://attacker.example",
        )
        self.assertEqual(cross_site.status_code, 403)

    def test_refresh_rotates_cookie_and_rejects_replay(self):
        registration = self.register()
        old_cookie = registration.cookies[settings.AUTH_REFRESH_COOKIE_NAME].value
        first = self.client.post(
            "/api/v1/auth/refresh/", {}, format="json", HTTP_X_CSRFTOKEN=self.csrf_token,
            HTTP_AUTHORIZATION="Bearer invalid-or-expired-access-token",
        )
        self.assertEqual(first.status_code, 200)
        self.assertIn("access", first.data)
        self.assertEqual(first.data["user"]["email"], "buyer@example.com")
        new_cookie = first.cookies[settings.AUTH_REFRESH_COOKIE_NAME].value
        self.assertNotEqual(old_cookie, new_cookie)
        self.assertTrue(
            BlacklistedToken.objects.filter(token__jti=RefreshToken(old_cookie, verify=False)["jti"]).exists()
        )
        self.client.cookies[settings.AUTH_REFRESH_COOKIE_NAME] = old_cookie
        replay = self.post("/api/v1/auth/refresh/")
        self.assertEqual(replay.status_code, 401)
        self.assertEqual(replay.data["error"]["code"], "AUTHENTICATION_REQUIRED")
        self.client.cookies[settings.AUTH_REFRESH_COOKIE_NAME] = new_cookie
        self.assertEqual(self.post("/api/v1/auth/refresh/").status_code, 200)

    def test_logout_revokes_refresh_cookie(self):
        registration = self.register()
        old_cookie = registration.cookies[settings.AUTH_REFRESH_COOKIE_NAME].value
        access = registration.data["access"]
        response = self.post("/api/v1/auth/logout/")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.cookies[settings.AUTH_REFRESH_COOKIE_NAME].value, "")
        self.client.cookies[settings.AUTH_REFRESH_COOKIE_NAME] = old_cookie
        self.assertEqual(self.post("/api/v1/auth/refresh/").status_code, 401)
        self.assertEqual(
            self.client.get("/api/v1/account/profile/", HTTP_AUTHORIZATION=f"Bearer {access}").status_code, 200
        )

    def test_profile_requires_bearer_and_enforces_customer_staff_separation(self):
        registration = self.register()
        access = registration.data["access"]
        anonymous = self.client.get("/api/v1/account/profile/")
        self.assertEqual(anonymous.status_code, 401)
        self.assertEqual(anonymous.data["error"]["code"], "AUTHENTICATION_REQUIRED")
        customer = self.client.get("/api/v1/account/profile/", HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(customer.status_code, 200)
        self.assertEqual(customer.data["email"], "buyer@example.com")
        denied = self.client.get("/api/v1/staff/profile/", HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.data["error"]["code"], "PERMISSION_DENIED")

        staff = get_user_model().objects.create_user(
            email="staff@example.com", password="a-strong-test-password", full_name="Staff", is_staff=True
        )
        login = self.post("/api/v1/auth/login/", {"email": staff.email, "password": "a-strong-test-password"})
        self.assertEqual(login.status_code, 200)
        staff_access = login.data["access"]
        allowed = self.client.get("/api/v1/staff/profile/", HTTP_AUTHORIZATION=f"Bearer {staff_access}")
        self.assertEqual(allowed.status_code, 200)
        self.assertTrue(allowed.data["is_staff"])
        denied = self.client.get("/api/v1/account/profile/", HTTP_AUTHORIZATION=f"Bearer {staff_access}")
        self.assertEqual(denied.status_code, 403)

        staff.is_staff = False
        staff.save(update_fields=["is_staff"])
        stale_role = self.client.get("/api/v1/staff/profile/", HTTP_AUTHORIZATION=f"Bearer {staff_access}")
        self.assertEqual(stale_role.status_code, 403)

    def test_disabling_user_blocks_existing_access_and_refresh(self):
        registration = self.register()
        user = get_user_model().objects.get(email="buyer@example.com")
        user.is_active = False
        user.save(update_fields=["is_active"])
        access = registration.data["access"]
        self.assertEqual(
            self.client.get("/api/v1/account/profile/", HTTP_AUTHORIZATION=f"Bearer {access}").status_code, 401
        )
        self.assertEqual(self.post("/api/v1/auth/refresh/").status_code, 401)

    def test_password_change_revokes_existing_access_and_refresh(self):
        registration = self.register()
        user = get_user_model().objects.get(email="buyer@example.com")
        user.set_password("another-strong-test-password")
        user.save(update_fields=["password"])
        access = registration.data["access"]
        self.assertEqual(
            self.client.get("/api/v1/account/profile/", HTTP_AUTHORIZATION=f"Bearer {access}").status_code, 401
        )
        self.assertEqual(self.post("/api/v1/auth/refresh/").status_code, 401)


class ConcurrentRefreshTests(TransactionTestCase):
    def test_same_refresh_token_can_rotate_only_once(self):
        user = get_user_model().objects.create_user(
            email="buyer@example.com", password="a-strong-test-password", full_name="Buyer"
        )
        _, raw_refresh = issue_tokens(user)
        barrier = Barrier(2)

        def attempt():
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                try:
                    rotate_refresh(raw_refresh)
                except AuthenticationError:
                    return False
                return True
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: attempt(), range(2)))

        self.assertEqual(sorted(results), [False, True])
