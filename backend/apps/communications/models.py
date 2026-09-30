import uuid

from django.db import models
from django.utils import timezone


class EmailOutbox(models.Model):
    class EventType(models.TextChoices):
        ORDER_PLACED = "ORDER_PLACED", "Order placed"
        ORDER_STATUS_CHANGED = "ORDER_STATUS_CHANGED", "Order status changed"
        ORDER_CANCELLED = "ORDER_CANCELLED", "Order cancelled"
        SURVEY_CONFIRMED = "SURVEY_CONFIRMED", "Survey confirmed"
        SURVEY_CHANGED = "SURVEY_CHANGED", "Survey changed"
        SURVEY_CANCELLED = "SURVEY_CANCELLED", "Survey cancelled"
        PASSWORD_RESET = "PASSWORD_RESET", "Password reset"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    event_type = models.CharField(max_length=32, choices=EventType.choices)
    order = models.ForeignKey("orders.Order", null=True, blank=True, on_delete=models.SET_NULL, related_name="email_events")
    survey_booking = models.ForeignKey(
        "surveys.SurveyBooking", null=True, blank=True, on_delete=models.SET_NULL, related_name="email_events",
    )
    recipient = models.EmailField()
    template_name = models.CharField(max_length=100)
    context = models.JSONField(default=dict)
    dedupe_key = models.CharField(max_length=200, unique=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    attempt_count = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now, null=True, blank=True)
    last_error = models.CharField(max_length=300, blank=True)
    claim_token = models.UUIDField(null=True, blank=True, default=None)
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["status", "next_attempt_at", "id"])]
        constraints = [
            models.CheckConstraint(condition=models.Q(attempt_count__gte=0), name="email_attempts_nonnegative"),
        ]

    def __str__(self):
        return f"{self.event_type} to {self.recipient} ({self.status})"


EMAIL_OUTBOX_STATUS_CHOICES = EmailOutbox.Status.choices
