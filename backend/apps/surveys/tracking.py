import uuid

from django.conf import settings
from django.core import signing
from django.http import Http404

from .models import SurveyBooking


GUEST_TRACKING_SALT = "octacam.surveys.guest-tracking"


def build_guest_tracking_url(booking):
    if booking.user_id is not None:
        raise ValueError("Guest tracking links are only available for guest bookings")
    token = signing.Signer(salt=GUEST_TRACKING_SALT).sign_object(
        {"public_id": str(booking.public_id), "nonce": str(booking.guest_link_nonce)},
    )
    return f"{settings.PUBLIC_SITE_URL}/api/v1/surveys/track/{token}/"


def get_booking_for_guest_token(token):
    if not isinstance(token, str) or len(token) > 512:
        raise Http404
    try:
        payload = signing.Signer(salt=GUEST_TRACKING_SALT).unsign_object(token)
        if not isinstance(payload, dict):
            raise ValueError
        public_id = uuid.UUID(payload["public_id"])
        nonce = uuid.UUID(payload["nonce"])
    except (signing.BadSignature, KeyError, TypeError, ValueError, AttributeError) as exc:
        raise Http404 from exc
    booking = SurveyBooking.objects.select_related("slot").filter(
        public_id=public_id, guest_link_nonce=nonce, user__isnull=True,
    ).first()
    if booking is None:
        raise Http404
    return booking
