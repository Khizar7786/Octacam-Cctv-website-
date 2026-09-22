import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403


DEBUG = False
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
ALLOWED_HOSTS = [host.strip() for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if host.strip()]

if not SECRET_KEY or not ALLOWED_HOSTS or not os.environ.get("DATABASE_URL"):
    raise ImproperlyConfigured("Production requires DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS, and DATABASE_URL")

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
