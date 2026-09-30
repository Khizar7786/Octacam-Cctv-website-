from urllib.parse import urlencode
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


class PermanentEmailError(Exception):
    """The saved event cannot be delivered by retrying it."""


def password_fingerprint(user):
    return salted_hmac("octacam.password-reset-outbox", f"{user.password}:{user.email.lower()}").hexdigest()


def render_email(message):
    if message.template_name == "order_placed" and message.event_type == "ORDER_PLACED":
        return render_order_placed_email(message)
    if message.template_name == "order_status_changed" and message.event_type == "ORDER_STATUS_CHANGED":
        return render_order_status_changed_email(message)
    if message.template_name == "password_reset" and message.event_type == "PASSWORD_RESET":
        return render_password_reset_email(message)
    raise PermanentEmailError("Unsupported email template")


def render_order_placed_email(message):
    from apps.orders.models import Order
    from apps.orders.tracking import build_guest_tracking_url

    order_id = message.context.get("order_id")
    if isinstance(order_id, bool) or not isinstance(order_id, int) or order_id < 1:
        raise PermanentEmailError("Order reference is invalid")
    order = Order.objects.prefetch_related("items").filter(pk=order_id).first()
    if order is None:
        raise PermanentEmailError("Order is no longer available")
    if order.customer_email.casefold() != message.recipient.casefold():
        raise PermanentEmailError("Order recipient does not match")

    guest_tracking_url = None
    if order.user_id is None:
        guest_tracking_url = build_guest_tracking_url(order)
    context = {
        "customer_name": order.customer_name,
        "reference": order.reference,
        "items": [
            {
                "product_name": item.product_name,
                "sku": item.sku,
                "quantity": item.quantity,
                "unit_price": f"{item.unit_price:,.2f}",
                "line_subtotal": f"{item.line_subtotal:,.2f}",
            }
            for item in order.items.all()
        ],
        "subtotal": f"{order.subtotal:,.2f}",
        "tax_total": f"{order.tax_total:,.2f}",
        "shipping_fee": f"{order.shipping_fee:,.2f}",
        "grand_total": f"{order.grand_total:,.2f}",
        "guest_tracking_url": guest_tracking_url,
    }
    subject = render_to_string("communications/email/order_placed_subject.txt", context).strip()
    body = render_to_string("communications/email/order_placed.txt", context)
    return subject, body


def render_order_status_changed_email(message):
    from apps.orders.models import Order
    from apps.orders.tracking import build_guest_tracking_url

    snapshot = message.context
    if not isinstance(snapshot, dict):
        raise PermanentEmailError("Order status event is invalid")
    order_id = snapshot.get("order_id")
    if isinstance(order_id, bool) or not isinstance(order_id, int) or order_id < 1:
        raise PermanentEmailError("Order reference is invalid")
    from_status = snapshot.get("from_status")
    to_status = snapshot.get("to_status")
    if (
        from_status not in Order.Status.values
        or to_status not in Order.Status.values
        or from_status == to_status
    ):
        raise PermanentEmailError("Order status event is invalid")
    courier_fields = ("courier_name", "tracking_number", "tracking_url")
    if any(field not in snapshot or not isinstance(snapshot[field], str) for field in courier_fields):
        raise PermanentEmailError("Courier snapshot is invalid")

    order = Order.objects.filter(pk=order_id).first()
    if order is None or message.order_id != order.pk:
        raise PermanentEmailError("Order is no longer available")
    if order.customer_email.casefold() != message.recipient.casefold():
        raise PermanentEmailError("Order recipient does not match")

    context = {
        "customer_name": order.customer_name,
        "reference": order.reference,
        "from_status": Order.Status(from_status).label,
        "to_status": Order.Status(to_status).label,
        "courier_name": snapshot["courier_name"],
        "tracking_number": snapshot["tracking_number"],
        "tracking_url": snapshot["tracking_url"],
        "guest_tracking_url": build_guest_tracking_url(order) if order.user_id is None else None,
    }
    subject = render_to_string("communications/email/order_status_changed_subject.txt", context).strip()
    body = render_to_string("communications/email/order_status_changed.txt", context)
    return subject, body


def render_password_reset_email(message):
    if timezone.now() - message.created_at > timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT):
        raise PermanentEmailError("Password reset request expired")
    user = get_user_model().objects.filter(pk=message.context.get("user_id"), is_active=True).first()
    if not user or not user.has_usable_password() or user.email != message.recipient:
        raise PermanentEmailError("Account is no longer available")
    if not constant_time_compare(password_fingerprint(user), message.context.get("password_fingerprint", "")):
        raise PermanentEmailError("Password changed after reset request")
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_url = f"{settings.PUBLIC_SITE_URL}/reset-password?{urlencode({'uid': uid, 'token': token})}"
    context = {"reset_url": reset_url, "timeout_minutes": settings.PASSWORD_RESET_TIMEOUT // 60}
    subject = render_to_string("communications/email/password_reset_subject.txt", context).strip()
    body = render_to_string("communications/email/password_reset.txt", context)
    return subject, body


def deliver_email(message):
    subject, body = render_email(message)
    sent = send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [message.recipient], fail_silently=False)
    if sent != 1:
        raise RuntimeError("Email backend did not accept the message")
