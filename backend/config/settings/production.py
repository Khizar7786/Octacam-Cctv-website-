import os
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403


DEBUG = False
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
ALLOWED_HOSTS = [host.strip() for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if host.strip()]

if len(SECRET_KEY) < 50 or not ALLOWED_HOSTS or not os.environ.get("DATABASE_URL"):
    raise ImproperlyConfigured(
        "Production requires a DJANGO_SECRET_KEY of at least 50 characters, DJANGO_ALLOWED_HOSTS, and DATABASE_URL"
    )

media_storage_backend = os.environ.get("DJANGO_MEDIA_STORAGE_BACKEND", "").strip()
if not media_storage_backend or media_storage_backend == "django.core.files.storage.FileSystemStorage":
    raise ImproperlyConfigured("Production requires a configured object-storage media backend")
public_site = urlsplit(os.environ.get("PUBLIC_SITE_URL", ""))
if (public_site.scheme != "https" or not public_site.hostname or public_site.username
        or public_site.password or public_site.query or public_site.fragment
        or public_site.path not in {"", "/"}):
    raise ImproperlyConfigured("Production requires an HTTPS PUBLIC_SITE_URL for password reset links")
if not EMAIL_BACKEND or EMAIL_BACKEND in {
    "django.core.mail.backends.console.EmailBackend",
    "django.core.mail.backends.locmem.EmailBackend",
    "django.core.mail.backends.filebased.EmailBackend",
    "django.core.mail.backends.dummy.EmailBackend",
} or not os.environ.get("DEFAULT_FROM_EMAIL"):
    raise ImproperlyConfigured("Production requires a delivery EMAIL_BACKEND and DEFAULT_FROM_EMAIL")
STORAGES = {
    "default": {"BACKEND": media_storage_backend},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
AUTH_REFRESH_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
