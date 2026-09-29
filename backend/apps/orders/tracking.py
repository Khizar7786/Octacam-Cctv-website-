import uuid

from django.core import signing
from django.http import Http404


GUEST_TRACKING_SALT = "octacam.orders.guest-tracking"


def make_guest_tracking_token(order):
    """Issue a revocable, order-scoped link for a guest order."""
    if order.user_id is not None:
        raise ValueError("Guest tracking links are only available for guest orders")
    return signing.dumps(
        {"public_id": str(order.public_id), "nonce": str(order.guest_link_nonce)},
        salt=GUEST_TRACKING_SALT,
    )


def get_order_for_guest_token(token):
    """Resolve a signed guest link without exposing whether an order exists."""
    from apps.orders.models import Order

    if not isinstance(token, str) or len(token) > 512:
        raise Http404
    try:
        payload = signing.loads(token, salt=GUEST_TRACKING_SALT)
        if not isinstance(payload, dict):
            raise ValueError
        public_id = uuid.UUID(payload["public_id"])
        nonce = uuid.UUID(payload["nonce"])
    except (signing.BadSignature, KeyError, TypeError, ValueError, AttributeError) as exc:
        raise Http404 from exc
    order = Order.objects.filter(
        public_id=public_id,
        guest_link_nonce=nonce,
        user__isnull=True,
    ).first()
    if order is None:
        raise Http404
    return order
