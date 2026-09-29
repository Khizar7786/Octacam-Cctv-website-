from rest_framework import serializers

from apps.communications.models import EmailOutbox


class EmailOutboxSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailOutbox
        fields = (
            "id", "event_type", "recipient", "template_name", "status", "attempt_count",
            "next_attempt_at", "last_error", "created_at", "sent_at",
        )
        read_only_fields = fields
