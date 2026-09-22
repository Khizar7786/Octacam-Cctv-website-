from django.contrib.auth import authenticate, get_user_model
from django.test import TestCase


class UserModelTests(TestCase):
    def test_email_is_login_identifier(self):
        user = get_user_model().objects.create_user(
            email="BUYER@Example.COM", password="a-strong-test-password", full_name="Test Buyer"
        )
        self.assertEqual(user.email, "buyer@example.com")
        self.assertIsNone(getattr(user, "username", None))
        self.assertEqual(authenticate(username="buyer@example.com", password="a-strong-test-password"), user)

    def test_superuser_requires_staff_and_superuser_flags(self):
        with self.assertRaises(ValueError):
            get_user_model().objects.create_superuser(
                email="staff@example.com", password="a-strong-test-password", full_name="Staff", is_staff=False
            )
