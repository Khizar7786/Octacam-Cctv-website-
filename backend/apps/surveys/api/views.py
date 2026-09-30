from django.conf import settings
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api.serializers import ApiErrorSerializer
from apps.core.permissions import IsStaff
from apps.surveys.selectors import public_available_slots, staff_slots
from apps.surveys.services import (
    SurveyConfigurationError, SurveySlotConflict, create_slot, update_slot,
)

from .serializers import (
    PublicSurveySlotSerializer, StaffSurveySlotCreateSerializer,
    StaffSurveySlotPatchSerializer, StaffSurveySlotSerializer,
)


PRIVATE_RESPONSE_HEADERS = [
    OpenApiParameter(name="Cache-Control", location=OpenApiParameter.HEADER, response=True,
                     description="private, no-store"),
    OpenApiParameter(name="X-Robots-Tag", location=OpenApiParameter.HEADER, response=True,
                     description="noindex, nofollow"),
]


class SurveySlotPagination(PageNumberPagination):
    page_size = settings.SURVEY_SLOT_PAGE_SIZE


class PrivateSurveyResponseMixin:
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        response["X-Robots-Tag"] = "noindex, nofollow"
        return response


def slot_conflict_response(exc):
    return Response({"error": {"code": exc.code, "message": exc.message, "fields": {}}}, status=409)


def configuration_response():
    return Response({
        "error": {
            "code": "SURVEY_NOT_CONFIGURED",
            "message": "An approved survey slot duration must be configured before saving this time.",
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
