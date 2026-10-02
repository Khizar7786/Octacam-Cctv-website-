from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.communications.models import EmailOutbox
from apps.communications.services import retry_block_reason


class EmailOutboxSerializer(serializers.ModelSerializer):
    retry_available = serializers.SerializerMethodField()

    @extend_schema_field(serializers.BooleanField)
    def get_retry_available(self, message):
        return retry_block_reason(message) is None

    class Meta:
        model = EmailOutbox
        fields = (
            "id", "event_type", "recipient", "template_name", "status", "attempt_count",
            "next_attempt_at", "last_error", "created_at", "sent_at", "retry_available",
        )
        read_only_fields = fields
