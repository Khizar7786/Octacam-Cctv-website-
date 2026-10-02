from django.conf import settings
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import generics
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api.serializers import ApiErrorSerializer
from apps.communications.models import EmailOutbox
from apps.communications.services import retry_email
from apps.core.permissions import IsStaff
from apps.core.api.staff_response import PRIVATE_STAFF_HEADERS, PrivateStaffResponseMixin

from .serializers import EmailOutboxSerializer


class EmailPagination(PageNumberPagination):
    page_size = settings.STAFF_ORDER_PAGE_SIZE


@extend_schema_view(get=extend_schema(
    tags=["staff"], parameters=[OpenApiParameter("status", str, enum=EmailOutbox.Status.values),
                                 *PRIVATE_STAFF_HEADERS],
    responses={200: EmailOutboxSerializer(many=True), 400: ApiErrorSerializer,
               401: ApiErrorSerializer, 403: ApiErrorSerializer},
))
class StaffEmailList(PrivateStaffResponseMixin, generics.ListAPIView):
    permission_classes = [IsStaff]
    serializer_class = EmailOutboxSerializer
    pagination_class = EmailPagination

    def get_queryset(self):
        status = self.request.query_params.get("status")
        if status and status not in EmailOutbox.Status.values:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"status": ["Choose pending, sent, or failed."]})
        queryset = EmailOutbox.objects.all()
        return queryset.filter(status=status) if status else queryset


class StaffEmailRetry(PrivateStaffResponseMixin, APIView):
    permission_classes = [IsStaff]

    @extend_schema(
        tags=["staff"], request=None, parameters=PRIVATE_STAFF_HEADERS,
        responses={200: EmailOutboxSerializer, 400: ApiErrorSerializer,
                   401: ApiErrorSerializer, 403: ApiErrorSerializer, 404: ApiErrorSerializer},
    )
    def post(self, request, email_id):
        message = retry_email(email_id=email_id, actor=request.user)
        return Response(EmailOutboxSerializer(message).data)
