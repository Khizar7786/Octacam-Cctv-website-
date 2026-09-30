import uuid

from django.conf import settings
from django.db import models


class SurveySlot(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    starts_at = models.DateTimeField(unique=True)
    ends_at = models.DateTimeField()
    capacity = models.PositiveIntegerField()
    is_open = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="created_survey_slots",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["starts_at", "id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(capacity__gt=0), name="survey_slot_positive_capacity"),
            models.CheckConstraint(condition=models.Q(ends_at__gt=models.F("starts_at")), name="survey_slot_end_after_start"),
        ]

    def __str__(self):
        return f"Survey slot {self.public_id}"


class SurveyBooking(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmed"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    reference = models.CharField(max_length=24, unique=True, editable=False)
    slot = models.ForeignKey(SurveySlot, on_delete=models.PROTECT, related_name="bookings")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="survey_bookings",
    )
    related_order = models.ForeignKey(
        "orders.Order", null=True, blank=True, on_delete=models.PROTECT, related_name="survey_bookings",
    )
    customer_name = models.CharField(max_length=160)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=40)
    site_address_line1 = models.CharField(max_length=255)
    site_address_line2 = models.CharField(max_length=255, blank=True)
    site_area = models.CharField(max_length=120, blank=True)
    site_city = models.CharField(max_length=120)
    needs_description = models.TextField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.CONFIRMED)
    internal_notes = models.TextField(blank=True)
    idempotency_key = models.UUIDField(unique=True)
    request_fingerprint = models.CharField(max_length=64)
    guest_link_nonce = models.UUIDField(default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["slot", "status"])]

    def __str__(self):
        return self.reference
