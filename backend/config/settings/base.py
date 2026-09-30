import os
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from django.utils.log import DEFAULT_LOGGING


BASE_DIR = Path(__file__).resolve().parents[2]


def database_config():
    url = os.environ.get("DATABASE_URL")
    if url:
        parsed = urlsplit(url)
        if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname or not parsed.path.strip("/"):
            raise ValueError("DATABASE_URL must be a PostgreSQL URL with a host and database name")
        query = parse_qs(parsed.query)
        options = {"connect_timeout": 5}
        if "sslmode" in query:
            options["sslmode"] = query["sslmode"][-1]
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(parsed.path.lstrip("/")),
            "USER": unquote(parsed.username or ""),
            "PASSWORD": unquote(parsed.password or ""),
            "HOST": parsed.hostname,
            "PORT": parsed.port or 5432,
            "OPTIONS": options,
        }
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "octacam"),
        "USER": os.environ.get("POSTGRES_USER", "octacam"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "octacam_dev"),
        "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.environ.get("POSTGRES_PORT", "5433"),
        "OPTIONS": {"connect_timeout": 5},
    }


INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "rest_framework_simplejwt.token_blacklist",
    "apps.accounts",
    "apps.audit",
    "apps.catalog",
    "apps.communications",
    "apps.orders",
    "apps.surveys",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

LOGGING = deepcopy(DEFAULT_LOGGING)
LOGGING["filters"]["redact_guest_tracking_token"] = {"()": "apps.orders.logging.RedactGuestTrackingToken"}
for handler_name in ("console", "django.server", "mail_admins"):
    LOGGING["handlers"][handler_name].setdefault("filters", []).append("redact_guest_tracking_token")

ROOT_URLCONF = "config.urls"
CSRF_FAILURE_VIEW = "apps.core.api.exception_handler.csrf_failure"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
    }
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {"default": database_config()}
AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.api.exception_handler.api_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "NUM_PROXIES": 0,
    "DEFAULT_THROTTLE_RATES": {
        "auth_register": "5/hour",
        "auth_login": "10/min",
        "auth_refresh": "30/min",
        "auth_password_reset": "5/hour",
        "auth_password_reset_confirm": "10/hour",
        "checkout_quote": "60/hour",
        "checkout_place": "10/hour",
    },
}
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=5),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "CHECK_REVOKE_TOKEN": True,
}
AUTH_REFRESH_COOKIE_NAME = "octacam_refresh"
AUTH_REFRESH_COOKIE_PATH = "/api/v1/auth/"
PASSWORD_RESET_TIMEOUT = 60 * 60
PUBLIC_SITE_URL = os.environ.get("PUBLIC_SITE_URL", "http://127.0.0.1:8000").rstrip("/")
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "OctaCam local <noreply@localhost>")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "false").lower() == "true"
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "false").lower() == "true"
EMAIL_TIMEOUT = 10
EMAIL_OUTBOX_MAX_ATTEMPTS = 5
EMAIL_OUTBOX_CLAIM_SECONDS = 300
CHECKOUT_SHIPPING_FEE = os.environ.get("CHECKOUT_SHIPPING_FEE")
CHECKOUT_TAX_RATE_PERCENT = os.environ.get("CHECKOUT_TAX_RATE_PERCENT")
CHECKOUT_SHIPPING_TAXABLE = os.environ.get("CHECKOUT_SHIPPING_TAXABLE")
SURVEY_SLOT_DURATION_MINUTES = os.environ.get("SURVEY_SLOT_DURATION_MINUTES")
SPECTACULAR_SETTINGS = {
    "TITLE": "OctaCam API",
    "VERSION": "1.0.0",
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
    "COMPONENT_SPLIT_REQUEST": True,
    "ENUM_NAME_OVERRIDES": {
        "OrderStatusEnum": "apps.orders.models.ORDER_STATUS_CHOICES",
        "EmailOutboxStatusEnum": "apps.communications.models.EMAIL_OUTBOX_STATUS_CHOICES",
    },
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Karachi"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
PRODUCT_IMAGE_MAX_BYTES = 5 * 1024 * 1024
PRODUCT_IMAGE_MAX_WIDTH = 6000
PRODUCT_IMAGE_MAX_HEIGHT = 6000
PRODUCT_IMAGE_MAX_PIXELS = 24_000_000
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CATALOG_PAGE_SIZE = 20
ACCOUNT_ORDER_PAGE_SIZE = 20
STAFF_ORDER_PAGE_SIZE = 20
SURVEY_SLOT_PAGE_SIZE = 20
