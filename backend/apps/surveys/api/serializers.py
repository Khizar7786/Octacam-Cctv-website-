from zoneinfo import ZoneInfo

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.surveys.models import SurveyBooking, SurveySlot


KARACHI = ZoneInfo("Asia/Karachi")


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, dict):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError({key: ["This field is not supported."] for key in sorted(unknown)})
        return super().to_internal_value(data)


class OffsetDateTimeField(serializers.DateTimeField):
    def __init__(self, **kwargs):
        super().__init__(default_timezone=KARACHI, **kwargs)

    def to_internal_value(self, value):
        try:
            parsed = parse_datetime(value) if isinstance(value, str) else value
        except ValueError as exc:
            raise serializers.ValidationError("Enter a valid ISO 8601 date and time.") from exc
        if parsed is None or not hasattr(parsed, "utcoffset") or timezone.is_naive(parsed):
            raise serializers.ValidationError("Include an ISO 8601 date and time with a timezone offset.")
        return super().to_internal_value(value)


class PublicSurveySlotSerializer(serializers.ModelSerializer):
    starts_at = OffsetDateTimeField(read_only=True)
    ends_at = OffsetDateTimeField(read_only=True)

    class Meta:
        model = SurveySlot
        fields = ("public_id", "starts_at", "ends_at")
        read_only_fields = fields


class StaffSurveySlotSerializer(PublicSurveySlotSerializer):
    booked_count = serializers.SerializerMethodField()
    remaining_capacity = serializers.SerializerMethodField()

    class Meta(PublicSurveySlotSerializer.Meta):
        fields = (
            *PublicSurveySlotSerializer.Meta.fields, "capacity", "is_open",
            "booked_count", "remaining_capacity", "version", "created_by", "created_at", "updated_at",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.IntegerField)
    def get_booked_count(self, slot):
        if hasattr(slot, "booked_count"):
            return slot.booked_count
        return slot.bookings.exclude(status=SurveyBooking.Status.CANCELLED).count()

    @extend_schema_field(serializers.IntegerField)
    def get_remaining_capacity(self, slot):
        return slot.capacity - self.get_booked_count(slot)


class StaffSurveySlotCreateSerializer(StrictSerializer):
    starts_at = OffsetDateTimeField()
    capacity = serializers.IntegerField(min_value=1, max_value=2_147_483_647)
    is_open = serializers.BooleanField(required=False, default=True)


class StaffSurveySlotPatchSerializer(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=0)
    starts_at = OffsetDateTimeField(required=False)
    capacity = serializers.IntegerField(min_value=1, max_value=2_147_483_647, required=False)
    is_open = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if not any(field in attrs for field in ("starts_at", "capacity", "is_open")):
            raise serializers.ValidationError({"slot": ["Provide a slot field to change."]})
        return attrs
