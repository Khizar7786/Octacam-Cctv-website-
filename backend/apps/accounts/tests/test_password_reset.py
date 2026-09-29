import re
from datetime import datetime, timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.services import issue_tokens
from apps.communications.models import EmailOutbox
from apps.communications.services import process_email_batch


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    PUBLIC_SITE_URL="https://shop.example.test",
)
class PasswordResetTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            email="buyer@example.com", password="old-strong-test-password", full_name="Buyer",
        )
        self.inactive = get_user_model().objects.create_user(
            email="inactive@example.com", password="old-strong-test-password", full_name="Inactive",
            is_active=False,
        )
        self.client = APIClient(enforce_csrf_checks=True)
        self.csrf = self.client.get("/api/v1/auth/csrf/").data["csrfToken"]

    def request_reset(self, email):
        return self.client.post(
            "/api/v1/auth/password-reset/request/", {"email": email}, format="json",
            HTTP_X_CSRFTOKEN=self.csrf,
        )

    def confirm(self, **data):
        return self.client.post(
            "/api/v1/auth/password-reset/confirm/", data, format="json", HTTP_X_CSRFTOKEN=self.csrf,
        )

    def link_parts(self):
        link = re.search(r"https://\S+", mail.outbox[0].body).group(0)
        parsed = urlsplit(link)
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "shop.example.test")
        self.assertEqual(parsed.path, "/reset-password")
        parts = parse_qs(parsed.query)
        return parts["uid"][0], parts["token"][0]

    def test_reset_request_is_neutral_and_only_enqueues_for_active_account(self):
        responses = [
            self.request_reset("BUYER@example.com"),
            self.request_reset("missing@example.com"),
            self.request_reset("inactive@example.com"),
            self.request_reset("buyer@example.com"),
        ]
        self.assertEqual([response.status_code for response in responses], [202] * 4)
        self.assertEqual(len({str(response.data) for response in responses}), 1)
        self.assertEqual(EmailOutbox.objects.count(), 1)
        message = EmailOutbox.objects.get()
        self.assertEqual(message.event_type, "PASSWORD_RESET")
        self.assertEqual(message.recipient, self.user.email)
        self.assertNotIn("token", message.context)
        self.assertNotIn("new_password", message.context)
        self.assertNotIn(self.user.password, str(message.context))
        self.assertEqual(mail.outbox, [])

    def test_worker_sends_reset_link_and_confirmation_is_one_time(self):
        access, refresh = issue_tokens(self.user)
        self.assertEqual(self.request_reset(self.user.email).status_code, 202)
        self.assertEqual(process_email_batch(), ["sent"])
        self.assertEqual(len(mail.outbox), 1)
        uid, token = self.link_parts()
        message = EmailOutbox.objects.get()
        self.assertEqual(message.status, "sent")
        self.assertEqual(message.context, {})
        self.assertNotIn(token, str(message.context))

        weak = self.confirm(uid=uid, token=token, new_password="123")
        self.assertEqual(weak.status_code, 400)
        self.assertIn("new_password", weak.data["error"]["fields"])
        changed = self.confirm(uid=uid, token=token, new_password="new-strong-test-password-123")
        self.assertEqual(changed.status_code, 204)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("new-strong-test-password-123"))
        reused = self.confirm(uid=uid, token=token, new_password="another-strong-password-123")
        self.assertEqual(reused.status_code, 400)
        self.assertIn("token", reused.data["error"]["fields"])
        self.assertEqual(self.client.get(
            "/api/v1/account/profile/", HTTP_AUTHORIZATION=f"Bearer {access}",
        ).status_code, 401)
        self.client.cookies[settings.AUTH_REFRESH_COOKIE_NAME] = refresh
        self.assertEqual(self.client.post(
            "/api/v1/auth/refresh/", {}, format="json", HTTP_X_CSRFTOKEN=self.csrf,
        ).status_code, 401)

    def test_invalid_and_expired_tokens_cannot_change_password(self):
        self.request_reset(self.user.email)
        process_email_batch()
        uid, token = self.link_parts()
        self.assertEqual(self.confirm(
            uid=uid, token="invalid-token", new_password="new-strong-password-123",
        ).status_code, 400)
        self.assertEqual(self.confirm(
            uid="invalid", token=token, new_password="new-strong-password-123",
        ).status_code, 400)
        self.assertEqual(self.confirm(
            uid="YWJj", token=token, new_password="new-strong-password-123",
        ).status_code, 400)
        with patch.object(default_token_generator, "_now", return_value=datetime.now() + timedelta(hours=2)):
            expired = self.confirm(uid=uid, token=token, new_password="new-strong-password-123")
        self.assertEqual(expired.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("old-strong-test-password"))

    def test_failed_send_retries_without_changing_password_or_losing_event(self):
        self.request_reset(self.user.email)
        with patch("apps.communications.email.send_mail", side_effect=OSError("SMTP down")):
            self.assertEqual(process_email_batch(), ["failed"])
        message = EmailOutbox.objects.get()
        self.assertEqual(message.attempt_count, 1)
        self.assertEqual(message.status, "failed")
        self.assertTrue(self.user.check_password("old-strong-test-password"))
        self.assertEqual(len(mail.outbox), 0)
        EmailOutbox.objects.filter(pk=message.pk).update(next_attempt_at=message.created_at)
        self.assertEqual(process_email_batch(), ["sent"])
        self.assertEqual(len(mail.outbox), 1)

    def test_password_change_before_delivery_suppresses_stale_reset(self):
        self.request_reset(self.user.email)
        self.user.set_password("changed-before-send-password")
        self.user.save(update_fields=["password"])
        self.assertEqual(process_email_batch(), ["failed"])
        message = EmailOutbox.objects.get()
        self.assertEqual(message.status, "failed")
        self.assertIsNone(message.next_attempt_at)
        self.assertEqual(message.context, {})
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(self.request_reset(self.user.email).status_code, 202)
        self.assertEqual(EmailOutbox.objects.count(), 2)
        self.assertEqual(process_email_batch(), ["sent"])

    def test_old_queued_reset_is_not_sent_late(self):
        self.request_reset(self.user.email)
        EmailOutbox.objects.update(created_at=timezone.now() - timedelta(hours=2))
        self.assertEqual(process_email_batch(), ["failed"])
        message = EmailOutbox.objects.get()
        self.assertIsNone(message.next_attempt_at)
        self.assertEqual(message.context, {})
        self.assertEqual(mail.outbox, [])

    def test_csrf_and_rate_limit_protect_reset_request(self):
        missing_csrf = self.client.post(
            "/api/v1/auth/password-reset/request/", {"email": self.user.email}, format="json",
        )
        self.assertEqual(missing_csrf.status_code, 403)
        for _ in range(5):
            self.assertEqual(self.request_reset("missing@example.com").status_code, 202)
        limited = self.request_reset("missing@example.com")
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(EmailOutbox.objects.count(), 0)
