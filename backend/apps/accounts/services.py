from django.contrib.auth import get_user_model
from django.contrib.auth import password_validation
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.http import urlsafe_base64_decode
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.utils import get_md5_hash_password

from apps.core.exceptions import AuthenticationError
from apps.communications.email import password_fingerprint
from apps.communications.models import EmailOutbox
from apps.communications.services import enqueue_email


@transaction.atomic
def update_customer_profile(*, user, data):
    if set(data) - {"full_name", "phone"}:
        raise ValidationError({"profile": ["Only full_name and phone can be edited."]})
    current = get_user_model().objects.select_for_update().get(pk=user.pk)
    if not current.is_active or current.is_staff:
        raise PermissionDenied("Customer access is required.")
    for field, value in data.items():
        setattr(current, field, value)
    if data:
        current.save(update_fields=list(data))
    return current


def issue_tokens(user):
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token), str(refresh)


@transaction.atomic
def rotate_refresh(raw_token):
    try:
        old = RefreshToken(raw_token)
        outstanding = OutstandingToken.objects.select_for_update().get(jti=old["jti"])
        if BlacklistedToken.objects.filter(token=outstanding).exists():
            raise AuthenticationError("Refresh token is invalid or expired.")
        user = get_user_model().objects.get(pk=old["user_id"], is_active=True)
        if api_settings.CHECK_REVOKE_TOKEN and old.get(api_settings.REVOKE_TOKEN_CLAIM) != get_md5_hash_password(
            user.password
        ):
            raise AuthenticationError("Refresh token is invalid or expired.")
        old.blacklist()
        access, refresh = issue_tokens(user)
        return user, access, refresh
    except (TokenError, OutstandingToken.DoesNotExist, get_user_model().DoesNotExist, KeyError) as exc:
        raise AuthenticationError("Refresh token is invalid or expired.") from exc


@transaction.atomic
def revoke_refresh(raw_token):
    try:
        token = RefreshToken(raw_token)
        outstanding = OutstandingToken.objects.select_for_update().get(jti=token["jti"])
        if not BlacklistedToken.objects.filter(token=outstanding).exists():
            token.blacklist()
    except (TokenError, OutstandingToken.DoesNotExist, KeyError):
        pass


@transaction.atomic
def request_password_reset(email):
    normalized = get_user_model().objects.normalize_email(email)
    user = get_user_model().objects.filter(email__iexact=normalized, is_active=True).first()
    if user is None or not user.has_usable_password():
        return
    bucket = int(timezone.now().timestamp()) // 300
    fingerprint = password_fingerprint(user)
    enqueue_email(
        event_type=EmailOutbox.EventType.PASSWORD_RESET,
        recipient=user.email,
        template_name="password_reset",
        context={"user_id": user.pk, "password_fingerprint": fingerprint},
        dedupe_key=f"password-reset:{user.pk}:{fingerprint[:16]}:{bucket}",
    )


@transaction.atomic
def confirm_password_reset(*, uid, token, new_password):
    try:
        user_id = urlsafe_base64_decode(uid).decode()
        user = get_user_model().objects.select_for_update().get(pk=user_id, is_active=True)
    except (ValueError, TypeError, OverflowError, UnicodeDecodeError, DjangoValidationError,
            get_user_model().DoesNotExist):
        raise ValidationError({"token": ["Reset link is invalid or expired."]}) from None
    if not default_token_generator.check_token(user, token):
        raise ValidationError({"token": ["Reset link is invalid or expired."]})
    try:
        password_validation.validate_password(new_password, user=user)
    except DjangoValidationError as exc:
        raise ValidationError({"new_password": exc.messages}) from exc
    user.set_password(new_password)
    user.save(update_fields=["password"])
