import uuid

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api.serializers import ApiErrorSerializer
from apps.core.permissions import IsStaff
from apps.surveys.selectors import public_available_slots, staff_slots, staff_bookings, booking_audit_history
from apps.surveys.booking_services import SurveyBookingConflict, book_survey
from apps.surveys.management_services import reschedule_survey, transition_survey, update_survey_notes
from apps.surveys.tracking import get_booking_for_guest_token
from apps.surveys.services import (
    SurveyConfigurationError, SurveySlotConflict, create_slot, update_slot,
)

from .serializers import (
    PublicSurveySlotSerializer, StaffSurveySlotCreateSerializer,
    StaffSurveySlotPatchSerializer, StaffSurveySlotSerializer,
    SurveyBookingRequestSerializer, SurveyBookingReceiptSerializer, GuestSurveyTrackingSerializer,
    StaffSurveyBookingSerializer, StaffSurveyBookingFilterSerializer, StaffSurveyBookingAuditSerializer,
    StaffSurveyRescheduleSerializer, StaffSurveyTransitionSerializer, StaffSurveyNotesSerializer,
)


PRIVATE_RESPONSE_HEADERS = [
    OpenApiParameter(name="Cache-Control", location=OpenApiParameter.HEADER, response=True,
                     description="private, no-store"),
    OpenApiParameter(name="X-Robots-Tag", location=OpenApiParameter.HEADER, response=True,
                     description="noindex, nofollow"),
    OpenApiParameter(name="Referrer-Policy", location=OpenApiParameter.HEADER, response=True,
                     description="no-referrer"),
]


class SurveySlotPagination(PageNumberPagination):
    page_size = settings.SURVEY_SLOT_PAGE_SIZE


class PrivateSurveyResponseMixin:
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        response["X-Robots-Tag"] = "noindex, nofollow"
        response["Referrer-Policy"] = "no-referrer"
        return response


def slot_conflict_response(exc):
    return Response({"error": {"code": exc.code, "message": exc.message, "fields": {}}}, status=409)


def configuration_response(message="An approved survey slot duration must be configured before saving this time."):
    return Response({
        "error": {
            "code": "SURVEY_NOT_CONFIGURED",
            "message": message,
            "fields": {},
        },
    }, status=503)


@extend_schema_view(get=extend_schema(
    tags=["surveys"],
    description="Upcoming open slots with space. Times are in Asia/Karachi; availability is not a reservation.",
    responses={200: PublicSurveySlotSerializer(many=True)},
))
class PublicSurveySlotList(generics.ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = PublicSurveySlotSerializer
    pagination_class = SurveySlotPagination

    def get_queryset(self):
        return public_available_slots()

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response


@extend_schema_view(
    get=extend_schema(
        tags=["staff"], parameters=PRIVATE_RESPONSE_HEADERS,
        responses={200: StaffSurveySlotSerializer(many=True), 401: ApiErrorSerializer, 403: ApiErrorSerializer},
    ),
    post=extend_schema(
        tags=["staff"], request=StaffSurveySlotCreateSerializer, parameters=PRIVATE_RESPONSE_HEADERS,
        responses={201: StaffSurveySlotSerializer, 400: ApiErrorSerializer, 401: ApiErrorSerializer,
                   403: ApiErrorSerializer, 409: ApiErrorSerializer, 503: ApiErrorSerializer},
    ),
)
class StaffSurveySlotList(PrivateSurveyResponseMixin, generics.ListAPIView):
    permission_classes = [IsStaff]
    serializer_class = StaffSurveySlotSerializer
    pagination_class = SurveySlotPagination

    def get_queryset(self):
        return staff_slots()

    def post(self, request):
        serializer = StaffSurveySlotCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            slot = create_slot(actor=request.user, **serializer.validated_data)
        except SurveyConfigurationError:
            return configuration_response()
        except SurveySlotConflict as exc:
            return slot_conflict_response(exc)
        return Response(StaffSurveySlotSerializer(slot).data, status=status.HTTP_201_CREATED)


class StaffSurveySlotDetail(PrivateSurveyResponseMixin, APIView):
    permission_classes = [IsStaff]

    @extend_schema(
        tags=["staff"], parameters=PRIVATE_RESPONSE_HEADERS,
        responses={200: StaffSurveySlotSerializer, 401: ApiErrorSerializer,
                   403: ApiErrorSerializer, 404: ApiErrorSerializer},
    )
    def get(self, request, public_id):
        slot = get_object_or_404(staff_slots(), public_id=public_id)
        return Response(StaffSurveySlotSerializer(slot).data)

    @extend_schema(
        tags=["staff"], request=StaffSurveySlotPatchSerializer, parameters=PRIVATE_RESPONSE_HEADERS,
        responses={200: StaffSurveySlotSerializer, 400: ApiErrorSerializer, 401: ApiErrorSerializer,
                   403: ApiErrorSerializer, 404: ApiErrorSerializer, 409: ApiErrorSerializer,
                   503: ApiErrorSerializer},
    )
    def patch(self, request, public_id):
        serializer = StaffSurveySlotPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        try:
            slot = update_slot(
                public_id=public_id, actor=request.user, expected_version=values["expected_version"],
                **{field: value for field, value in values.items() if field != "expected_version"},
            )
        except SurveyConfigurationError:
            return configuration_response()
        except SurveySlotConflict as exc:
            return slot_conflict_response(exc)
        return Response(StaffSurveySlotSerializer(slot).data)


@method_decorator(csrf_protect, name="dispatch")
class SurveyBookingCreateView(PrivateSurveyResponseMixin, APIView):
    permission_classes = [AllowAny]
    throttle_scope = "survey_booking"

    @extend_schema(
        tags=["surveys"], request=SurveyBookingRequestSerializer,
        description="Confirm a free standalone Lahore site survey. Installation is quoted afterward. Reuse the same key and body after an uncertain response.",
        parameters=[
            OpenApiParameter("Idempotency-Key", str, location=OpenApiParameter.HEADER, required=True,
                             description="A UUID for this intended booking; retain it for retries."),
            OpenApiParameter("X-CSRFToken", str, location=OpenApiParameter.HEADER, required=True,
                             description="Token from GET /api/v1/auth/csrf/."),
            *PRIVATE_RESPONSE_HEADERS,
        ],
        responses={201: SurveyBookingReceiptSerializer, 200: SurveyBookingReceiptSerializer,
                   400: ApiErrorSerializer, 401: ApiErrorSerializer, 403: ApiErrorSerializer,
                   409: ApiErrorSerializer, 429: ApiErrorSerializer, 503: ApiErrorSerializer},
    )
    def post(self, request):
        serializer = SurveyBookingRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            key = uuid.UUID(request.headers.get("Idempotency-Key", ""))
        except (ValueError, AttributeError):
            raise ValidationError({"idempotency_key": ["Send a valid UUID in the Idempotency-Key header."]}) from None
        try:
            booking, created = book_survey(data=serializer.validated_data, idempotency_key=key, user=request.user)
        except SurveyConfigurationError as exc:
            return configuration_response(str(exc))
        except SurveyBookingConflict as exc:
            return slot_conflict_response(exc)
        return Response(SurveyBookingReceiptSerializer(booking).data, status=201 if created else 200)


class GuestSurveyTrackingView(PrivateSurveyResponseMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=["surveys"], parameters=PRIVATE_RESPONSE_HEADERS,
        description="A private guest link exposes only this booking's limited status and time. Invalid or revoked links return 404.",
        responses={200: GuestSurveyTrackingSerializer, 404: ApiErrorSerializer},
    )
    def get(self, request, signed_token):
        return Response(GuestSurveyTrackingSerializer(get_booking_for_guest_token(signed_token)).data)


@extend_schema_view(get=extend_schema(
    tags=["staff"], parameters=[StaffSurveyBookingFilterSerializer, *PRIVATE_RESPONSE_HEADERS],
    responses={200: StaffSurveyBookingSerializer(many=True), 400: ApiErrorSerializer,
               401: ApiErrorSerializer, 403: ApiErrorSerializer},
))
class StaffSurveyBookingList(PrivateSurveyResponseMixin, generics.ListAPIView):
    permission_classes = [IsStaff]
    serializer_class = StaffSurveyBookingSerializer
    pagination_class = SurveySlotPagination

    def get_queryset(self):
        filters = StaffSurveyBookingFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        return staff_bookings(user=self.request.user, **filters.validated_data)


@extend_schema_view(get=extend_schema(
    tags=["staff"], parameters=PRIVATE_RESPONSE_HEADERS,
    responses={200: StaffSurveyBookingSerializer, 401: ApiErrorSerializer,
               403: ApiErrorSerializer, 404: ApiErrorSerializer},
))
class StaffSurveyBookingDetail(PrivateSurveyResponseMixin, generics.RetrieveAPIView):
    permission_classes = [IsStaff]
    serializer_class = StaffSurveyBookingSerializer
    lookup_field = "public_id"

    def get_queryset(self):
        return staff_bookings(user=self.request.user)


@extend_schema_view(get=extend_schema(
    tags=["staff"], parameters=PRIVATE_RESPONSE_HEADERS,
    responses={200: StaffSurveyBookingAuditSerializer(many=True), 401: ApiErrorSerializer,
               403: ApiErrorSerializer, 404: ApiErrorSerializer},
))
class StaffSurveyBookingHistory(PrivateSurveyResponseMixin, generics.ListAPIView):
    permission_classes = [IsStaff]
    serializer_class = StaffSurveyBookingAuditSerializer
    pagination_class = SurveySlotPagination

    def get_queryset(self):
        booking = get_object_or_404(staff_bookings(user=self.request.user), public_id=self.kwargs["public_id"])
        return booking_audit_history(booking=booking)


class StaffSurveyReschedule(PrivateSurveyResponseMixin, APIView):
    permission_classes = [IsStaff]

    @extend_schema(
        tags=["staff"], request=StaffSurveyRescheduleSerializer, parameters=PRIVATE_RESPONSE_HEADERS,
        responses={200: StaffSurveyBookingSerializer, 400: ApiErrorSerializer, 401: ApiErrorSerializer,
                   403: ApiErrorSerializer, 404: ApiErrorSerializer, 409: ApiErrorSerializer},
    )
    def post(self, request, public_id):
        serializer = StaffSurveyRescheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            booking = reschedule_survey(public_id=public_id, actor=request.user, **serializer.validated_data)
        except SurveyBookingConflict as exc:
            return slot_conflict_response(exc)
        return Response(StaffSurveyBookingSerializer(booking).data)


class StaffSurveyTransition(PrivateSurveyResponseMixin, APIView):
    permission_classes = [IsStaff]

    @extend_schema(
        tags=["staff"], request=StaffSurveyTransitionSerializer, parameters=PRIVATE_RESPONSE_HEADERS,
        responses={200: StaffSurveyBookingSerializer, 400: ApiErrorSerializer, 401: ApiErrorSerializer,
                   403: ApiErrorSerializer, 404: ApiErrorSerializer, 409: ApiErrorSerializer},
    )
    def post(self, request, public_id):
        serializer = StaffSurveyTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            booking = transition_survey(public_id=public_id, actor=request.user, **serializer.validated_data)
        except SurveyBookingConflict as exc:
            return slot_conflict_response(exc)
        return Response(StaffSurveyBookingSerializer(booking).data)


class StaffSurveyNotes(PrivateSurveyResponseMixin, APIView):
    permission_classes = [IsStaff]

    @extend_schema(
        tags=["staff"], request=StaffSurveyNotesSerializer, parameters=PRIVATE_RESPONSE_HEADERS,
        responses={200: StaffSurveyBookingSerializer, 400: ApiErrorSerializer, 401: ApiErrorSerializer,
                   403: ApiErrorSerializer, 404: ApiErrorSerializer, 409: ApiErrorSerializer},
    )
    def patch(self, request, public_id):
        serializer = StaffSurveyNotesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            booking = update_survey_notes(public_id=public_id, actor=request.user, **serializer.validated_data)
        except SurveyBookingConflict as exc:
            return slot_conflict_response(exc)
        return Response(StaffSurveyBookingSerializer(booking).data)
