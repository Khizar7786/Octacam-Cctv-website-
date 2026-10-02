from zoneinfo import ZoneInfo

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.audit.models import AuditEvent
from apps.orders.models import Order
from apps.surveys.models import SurveyBooking, SurveySlot
from apps.surveys.booking_services import INSTALLATION_NOTICE
from apps.surveys.tracking import build_guest_tracking_url


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


class SurveySiteRequestSerializer(StrictSerializer):
    slot_public_id = serializers.UUIDField()
    site_address_line1 = serializers.CharField(max_length=255)
    site_address_line2 = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    site_area = serializers.CharField(max_length=120)
    site_city = serializers.CharField(max_length=120)
    needs_description = serializers.CharField(max_length=3000)


class SurveyBookingRequestSerializer(SurveySiteRequestSerializer):
    customer_name = serializers.CharField(max_length=160)
    customer_email = serializers.EmailField()
    customer_phone = serializers.CharField(max_length=40)


class SurveyBookingSlotSerializer(serializers.Serializer):
    public_id = serializers.UUIDField(source="slot.public_id", read_only=True)
    starts_at = OffsetDateTimeField(source="scheduled_starts_at", read_only=True)
    ends_at = OffsetDateTimeField(source="scheduled_ends_at", read_only=True)


class SurveyBookingReceiptSerializer(serializers.ModelSerializer):
    slot = SurveyBookingSlotSerializer(source="*", read_only=True)
    service_type = serializers.CharField(read_only=True, default="site_survey")
    booking_fee = serializers.CharField(read_only=True, default="0.00")
    currency = serializers.CharField(read_only=True, default="PKR")
    installation_notice = serializers.CharField(read_only=True, default=INSTALLATION_NOTICE)
    guest_tracking_url = serializers.SerializerMethodField()

    class Meta:
        model = SurveyBooking
        fields = (
            "public_id", "reference", "status", "created_at", "slot", "customer_name",
            "customer_email", "customer_phone", "site_address_line1", "site_address_line2",
            "site_area", "site_city", "needs_description", "service_type", "booking_fee",
            "currency", "installation_notice", "guest_tracking_url",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_guest_tracking_url(self, booking):
        return build_guest_tracking_url(booking) if booking.user_id is None else None


class GuestSurveyTrackingSerializer(serializers.ModelSerializer):
    slot = SurveyBookingSlotSerializer(source="*", read_only=True)
    installation_notice = serializers.CharField(
        read_only=True, default="This booking is for a free site survey. Installation is quoted and scheduled afterward.",
    )

    class Meta:
        model = SurveyBooking
        fields = ("reference", "status", "slot", "site_area", "site_city", "installation_notice")
        read_only_fields = fields


class StaffSurveyBookingFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=SurveyBooking.Status.choices, required=False)
    q = serializers.CharField(max_length=80, required=False)
    upcoming = serializers.BooleanField(required=False, default=False)


class RelatedSurveyOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ("public_id", "reference")
        read_only_fields = fields


class StaffSurveyBookingSerializer(serializers.ModelSerializer):
    slot = SurveyBookingSlotSerializer(source="*", read_only=True)
    related_order = RelatedSurveyOrderSerializer(read_only=True, allow_null=True)

    class Meta:
        model = SurveyBooking
        fields = (
            "public_id", "reference", "status", "slot", "customer_name", "customer_email", "customer_phone",
            "site_address_line1", "site_address_line2", "site_area", "site_city", "needs_description",
            "related_order", "internal_notes", "version", "created_at", "updated_at",
        )
        read_only_fields = fields


class StaffSurveyRescheduleSerializer(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=0)
    slot_public_id = serializers.UUIDField()


class StaffSurveyTransitionSerializer(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=0)
    status = serializers.ChoiceField(choices=[SurveyBooking.Status.COMPLETED, SurveyBooking.Status.CANCELLED])


class StaffSurveyNotesSerializer(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=0)
    internal_notes = serializers.CharField(max_length=10000, allow_blank=True, trim_whitespace=False)


class StaffSurveyBookingAuditSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(source="actor.email", read_only=True, allow_null=True)

    class Meta:
        model = AuditEvent
        fields = ("id", "action", "actor_email", "before_data", "after_data", "metadata", "created_at")
        read_only_fields = fields
