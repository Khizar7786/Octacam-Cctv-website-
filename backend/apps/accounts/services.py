from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.utils import get_md5_hash_password

from apps.core.exceptions import AuthenticationError


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
