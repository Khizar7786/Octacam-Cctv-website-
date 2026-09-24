import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403


DEBUG = False
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
ALLOWED_HOSTS = [host.strip() for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if host.strip()]

if len(SECRET_KEY) < 50 or not ALLOWED_HOSTS or not os.environ.get("DATABASE_URL"):
    raise ImproperlyConfigured(
        "Production requires a DJANGO_SECRET_KEY of at least 50 characters, DJANGO_ALLOWED_HOSTS, and DATABASE_URL"
    )

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
AUTH_REFRESH_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
