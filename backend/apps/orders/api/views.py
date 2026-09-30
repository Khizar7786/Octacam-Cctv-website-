import uuid

from django.conf import settings
from django.shortcuts import get_object_or_404
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
from apps.core.permissions import IsCustomer, IsStaff
from apps.orders.fulfillment_services import (
    OrderCommandConflict, mark_order_cod_collected, transition_order, update_order_courier,
)
from apps.orders.models import Order
from apps.orders.pricing import CheckoutConfigurationError
from apps.orders.selectors import get_customer_orders, get_order_audit_history, get_staff_orders
from apps.orders.services import CheckoutConflict, create_quote, place_order
from apps.orders.tracking import get_order_for_guest_token

from .serializers import (
    CheckoutConflictSerializer, GuestOrderTrackingSerializer, OrderReceiptSerializer,
    PlaceOrderRequestSerializer, QuoteRequestSerializer, QuoteResponseSerializer,
    CustomerOrderDetailSerializer, CustomerOrderListSerializer,
    StaffOrderAuditSerializer, StaffOrderCodCollectedSerializer, StaffOrderCourierSerializer,
    StaffOrderDetailSerializer, StaffOrderFilterSerializer, StaffOrderListSerializer,
    StaffOrderTransitionSerializer,
)


CSRF_HEADER = OpenApiParameter(
    name="X-CSRFToken", type=str, location=OpenApiParameter.HEADER, required=True,
    description="Token returned by GET /api/v1/auth/csrf/.",
)
IDEMPOTENCY_HEADER = OpenApiParameter(
    name="Idempotency-Key", type=str, location=OpenApiParameter.HEADER, required=True,
    description="A new UUID for each intended order; reuse the same UUID and body to retry safely.",
)
PRIVATE_ORDER_RESPONSE_HEADERS = [
    OpenApiParameter(name="Cache-Control", location=OpenApiParameter.HEADER, response=True,
                     description="private, no-store"),
    OpenApiParameter(name="Referrer-Policy", location=OpenApiParameter.HEADER, response=True,
                     description="no-referrer"),
    OpenApiParameter(name="X-Robots-Tag", location=OpenApiParameter.HEADER, response=True,
                     description="noindex, nofollow"),
]


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


class PrivateOrderResponseMixin:
    """Keep customer order data out of caches and search results."""

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        response["Referrer-Policy"] = "no-referrer"
        response["X-Robots-Tag"] = "noindex, nofollow"
        return response


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
class CheckoutPlaceView(PrivateOrderResponseMixin, APIView):
    permission_classes = [AllowAny]
    throttle_scope = "checkout_place"

    @extend_schema(
        tags=["checkout"], request=PlaceOrderRequestSerializer,
        parameters=[CSRF_HEADER, IDEMPOTENCY_HEADER, *PRIVATE_ORDER_RESPONSE_HEADERS],
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


class GuestOrderTrackingView(PrivateOrderResponseMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=["orders"],
        description="A signed guest link grants access to this order's limited status only. Invalid and revoked links return 404.",
        parameters=PRIVATE_ORDER_RESPONSE_HEADERS,
        responses={200: GuestOrderTrackingSerializer, 404: ApiErrorSerializer},
    )
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


class StaffOrderPagination(PageNumberPagination):
    page_size = settings.STAFF_ORDER_PAGE_SIZE


STAFF_ORDER_FILTER_PARAMETERS = [
    OpenApiParameter("status", str, enum=Order.Status.values),
    OpenApiParameter("payment_status", str, enum=Order.PaymentStatus.values),
    OpenApiParameter("q", str, description="Find an order by all or part of its reference."),
]


@extend_schema_view(get=extend_schema(
    tags=["staff"], parameters=[*STAFF_ORDER_FILTER_PARAMETERS, *PRIVATE_ORDER_RESPONSE_HEADERS],
    responses={200: StaffOrderListSerializer(many=True), 400: ApiErrorSerializer,
               401: ApiErrorSerializer, 403: ApiErrorSerializer},
))
class StaffOrderListView(PrivateOrderResponseMixin, generics.ListAPIView):
    permission_classes = [IsStaff]
    serializer_class = StaffOrderListSerializer
    pagination_class = StaffOrderPagination

    def get_queryset(self):
        filters = StaffOrderFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        return get_staff_orders(user=self.request.user, **filters.validated_data)


@extend_schema_view(get=extend_schema(
    tags=["staff"], parameters=PRIVATE_ORDER_RESPONSE_HEADERS,
    responses={200: StaffOrderDetailSerializer, 401: ApiErrorSerializer,
               403: ApiErrorSerializer, 404: ApiErrorSerializer},
))
class StaffOrderDetailView(PrivateOrderResponseMixin, generics.RetrieveAPIView):
    permission_classes = [IsStaff]
    serializer_class = StaffOrderDetailSerializer
    lookup_field = "public_id"

    def get_queryset(self):
        return get_staff_orders(user=self.request.user).prefetch_related("items")


@extend_schema_view(get=extend_schema(
    tags=["staff"], parameters=PRIVATE_ORDER_RESPONSE_HEADERS,
    responses={200: StaffOrderAuditSerializer(many=True), 401: ApiErrorSerializer,
               403: ApiErrorSerializer, 404: ApiErrorSerializer},
))
class StaffOrderHistoryView(PrivateOrderResponseMixin, generics.ListAPIView):
    permission_classes = [IsStaff]
    serializer_class = StaffOrderAuditSerializer
    pagination_class = StaffOrderPagination

    def get_queryset(self):
        order = get_object_or_404(get_staff_orders(user=self.request.user), public_id=self.kwargs["public_id"])
        return get_order_audit_history(order=order)


def staff_order_conflict_response(exc):
    return Response({
        "error": {"code": exc.code, "message": exc.message, "fields": {}},
    }, status=status.HTTP_409_CONFLICT)


class StaffOrderCommandView(PrivateOrderResponseMixin, APIView):
    permission_classes = [IsStaff]

    def command_response(self, operation):
        try:
            order = operation()
        except OrderCommandConflict as exc:
            return staff_order_conflict_response(exc)
        return Response(StaffOrderDetailSerializer(order).data)


class StaffOrderTransitionView(StaffOrderCommandView):
    @extend_schema(
        tags=["staff"], request=StaffOrderTransitionSerializer, parameters=PRIVATE_ORDER_RESPONSE_HEADERS,
        responses={200: StaffOrderDetailSerializer, 400: ApiErrorSerializer, 401: ApiErrorSerializer,
                   403: ApiErrorSerializer, 404: ApiErrorSerializer, 409: ApiErrorSerializer},
    )
    def post(self, request, public_id):
        serializer = StaffOrderTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self.command_response(lambda: transition_order(
            public_id=public_id, actor=request.user, **serializer.validated_data,
        ))


class StaffOrderCourierView(StaffOrderCommandView):
    @extend_schema(
        tags=["staff"], request=StaffOrderCourierSerializer, parameters=PRIVATE_ORDER_RESPONSE_HEADERS,
        responses={200: StaffOrderDetailSerializer, 400: ApiErrorSerializer, 401: ApiErrorSerializer,
                   403: ApiErrorSerializer, 404: ApiErrorSerializer, 409: ApiErrorSerializer},
    )
    def patch(self, request, public_id):
        serializer = StaffOrderCourierSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        return self.command_response(lambda: update_order_courier(
            public_id=public_id, actor=request.user, expected_version=values["expected_version"],
            data={key: value for key, value in values.items() if key != "expected_version"},
        ))


class StaffOrderCodCollectedView(StaffOrderCommandView):
    @extend_schema(
        tags=["staff"], request=StaffOrderCodCollectedSerializer, parameters=PRIVATE_ORDER_RESPONSE_HEADERS,
        responses={200: StaffOrderDetailSerializer, 400: ApiErrorSerializer, 401: ApiErrorSerializer,
                   403: ApiErrorSerializer, 404: ApiErrorSerializer, 409: ApiErrorSerializer},
    )
    def post(self, request, public_id):
        serializer = StaffOrderCodCollectedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self.command_response(lambda: mark_order_cod_collected(
            public_id=public_id, actor=request.user, **serializer.validated_data,
        ))
