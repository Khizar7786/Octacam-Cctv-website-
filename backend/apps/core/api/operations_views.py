from django.conf import settings
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api.serializers import ApiErrorSerializer
from apps.core.api.staff_response import PRIVATE_STAFF_HEADERS, PrivateStaffResponseMixin
from apps.core.operations_selectors import get_staff_activity, get_staff_overview
from apps.core.permissions import IsStaff

from .operations_serializers import StaffActivitySerializer, StaffOverviewSerializer


class StaffActivityPagination(PageNumberPagination):
    page_size = settings.STAFF_ORDER_PAGE_SIZE


class StaffOverview(PrivateStaffResponseMixin, APIView):
    permission_classes = [IsStaff]

    @extend_schema(
        tags=["staff"], parameters=PRIVATE_STAFF_HEADERS,
        description="Five newest records per preview, with counts. Follow the paginated staff lists for more.",
        responses={200: StaffOverviewSerializer, 401: ApiErrorSerializer, 403: ApiErrorSerializer},
    )
    def get(self, request):
        overview = get_staff_overview(user=request.user, preview_size=settings.STAFF_OVERVIEW_PREVIEW_SIZE)
        return Response(StaffOverviewSerializer(overview).data)


@extend_schema_view(get=extend_schema(
    tags=["staff"], parameters=PRIVATE_STAFF_HEADERS,
    description="Newest audit actions first. Payload snapshots and private metadata are available only in resource history.",
    responses={200: StaffActivitySerializer(many=True), 401: ApiErrorSerializer, 403: ApiErrorSerializer},
))
class StaffActivityList(PrivateStaffResponseMixin, generics.ListAPIView):
    permission_classes = [IsStaff]
    serializer_class = StaffActivitySerializer
    pagination_class = StaffActivityPagination

    def get_queryset(self):
        return get_staff_activity(user=self.request.user)
