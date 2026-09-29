import uuid

from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api.serializers import ApiErrorSerializer
from apps.core.permissions import IsCustomer
from apps.orders.pricing import CheckoutConfigurationError
from apps.orders.selectors import get_customer_orders
from apps.orders.services import CheckoutConflict, create_quote, place_order
from apps.orders.tracking import get_order_for_guest_token

from .serializers import (
    CheckoutConflictSerializer, GuestOrderTrackingSerializer, OrderReceiptSerializer,
    PlaceOrderRequestSerializer, QuoteRequestSerializer, QuoteResponseSerializer,
    CustomerOrderDetailSerializer, CustomerOrderListSerializer,
)


CSRF_HEADER = OpenApiParameter(
    name="X-CSRFToken", type=str, location=OpenApiParameter.HEADER, required=True,
    description="Token returned by GET /api/v1/auth/csrf/.",
)
IDEMPOTENCY_HEADER = OpenApiParameter(
    name="Idempotency-Key", type=str, location=OpenApiParameter.HEADER, required=True,
    description="A new UUID for each intended order; reuse the same UUID and body to retry safely.",
)


def conflict_response(exc):
    return Response({
        "error": {"code": exc.code, "message": exc.message, "fields": {}},
        "current_quote": exc.current_quote,
    }, status=status.HTTP_409_CONFLICT)


def configuration_response():
    return Response({
        "error": {
            "code": "CHECKOUT_NOT_CONFIGURED",
            "message": "Checkout is unavailable until approved tax and shipping settings are configured.",
            "fields": {},
        },
    }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@method_decorator(csrf_protect, name="dispatch")
class CheckoutQuoteView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "checkout_quote"

    @extend_schema(
        tags=["checkout"], request=QuoteRequestSerializer, parameters=[CSRF_HEADER],
        responses={200: QuoteResponseSerializer, 400: ApiErrorSerializer, 403: ApiErrorSerializer,
                   409: CheckoutConflictSerializer, 429: ApiErrorSerializer, 503: ApiErrorSerializer},
    )
    def post(self, request):
        serializer = QuoteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            quote = create_quote(serializer.validated_data)
        except CheckoutConflict as exc:
            return conflict_response(exc)
        except CheckoutConfigurationError:
            return configuration_response()
        return Response(quote)


@method_decorator(csrf_protect, name="dispatch")
class CheckoutPlaceView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "checkout_place"

    @extend_schema(
        tags=["checkout"], request=PlaceOrderRequestSerializer, parameters=[CSRF_HEADER, IDEMPOTENCY_HEADER],
        responses={201: OrderReceiptSerializer, 200: OrderReceiptSerializer, 400: ApiErrorSerializer,
                   403: ApiErrorSerializer, 409: CheckoutConflictSerializer,
                   429: ApiErrorSerializer, 503: ApiErrorSerializer},
    )
    def post(self, request):
        serializer = PlaceOrderRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            key = uuid.UUID(request.headers.get("Idempotency-Key", ""))
        except (ValueError, AttributeError):
            raise ValidationError({"idempotency_key": ["Send a valid UUID in the Idempotency-Key header."]}) from None
        try:
            order, created = place_order(data=serializer.validated_data, idempotency_key=key, user=request.user)
        except CheckoutConflict as exc:
            return conflict_response(exc)
        except CheckoutConfigurationError:
            return configuration_response()
        return Response(OrderReceiptSerializer(order).data, status=201 if created else 200)


class GuestOrderTrackingView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=["orders"], responses={200: GuestOrderTrackingSerializer, 404: ApiErrorSerializer})
    def get(self, request, signed_token):
        order = get_order_for_guest_token(signed_token)
        return Response(GuestOrderTrackingSerializer(order).data)


class CustomerOrderPagination(PageNumberPagination):
    def get_page_size(self, request):
        return settings.ACCOUNT_ORDER_PAGE_SIZE


@extend_schema_view(get=extend_schema(
    tags=["account"], responses={200: CustomerOrderListSerializer(many=True), 401: ApiErrorSerializer, 403: ApiErrorSerializer},
))
class CustomerOrderListView(generics.ListAPIView):
    permission_classes = [IsCustomer]
    serializer_class = CustomerOrderListSerializer
    pagination_class = CustomerOrderPagination

    def get_queryset(self):
        return get_customer_orders(user=self.request.user)


@extend_schema_view(get=extend_schema(
    tags=["account"], responses={200: CustomerOrderDetailSerializer, 401: ApiErrorSerializer,
                               403: ApiErrorSerializer, 404: ApiErrorSerializer},
))
class CustomerOrderDetailView(generics.RetrieveAPIView):
    permission_classes = [IsCustomer]
    serializer_class = CustomerOrderDetailSerializer
    lookup_field = "public_id"

    def get_queryset(self):
        return get_customer_orders(user=self.request.user)
