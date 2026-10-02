from rest_framework import serializers

from apps.audit.models import AuditEvent
from apps.communications.api.serializers import EmailOutboxSerializer
from apps.orders.models import Order
from apps.surveys.api.serializers import OffsetDateTimeField
from apps.surveys.models import SurveyBooking


class OverviewOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ("public_id", "reference", "status", "payment_status", "grand_total", "placed_at")
        read_only_fields = fields


class OverviewSurveySerializer(serializers.ModelSerializer):
    scheduled_starts_at = OffsetDateTimeField(read_only=True)
    scheduled_ends_at = OffsetDateTimeField(read_only=True)

    class Meta:
        model = SurveyBooking
        fields = (
            "public_id", "reference", "status", "scheduled_starts_at", "scheduled_ends_at",
            "site_area", "site_city",
        )
        read_only_fields = fields


class StaffActivitySerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(source="actor.email", read_only=True, allow_null=True)

    class Meta:
        model = AuditEvent
        fields = ("id", "action", "resource_type", "resource_id", "actor_email", "created_at")
        read_only_fields = fields


class StaffOverviewSerializer(serializers.Serializer):
    placed_orders_count = serializers.IntegerField(read_only=True)
    open_orders_count = serializers.IntegerField(read_only=True)
    upcoming_surveys_count = serializers.IntegerField(read_only=True)
    failed_emails_count = serializers.IntegerField(read_only=True)
    recent_orders = OverviewOrderSerializer(many=True, read_only=True)
    upcoming_surveys = OverviewSurveySerializer(many=True, read_only=True)
    recent_activity = StaffActivitySerializer(many=True, read_only=True)
    failed_emails = EmailOutboxSerializer(many=True, read_only=True)
