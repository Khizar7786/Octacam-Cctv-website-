from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    resource_type = models.CharField(max_length=100)
    resource_id = models.CharField(max_length=100)
    action = models.CharField(max_length=100)
    before_data = models.JSONField(default=dict)
    after_data = models.JSONField(default=dict)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["resource_type", "resource_id", "created_at"])]

    def __str__(self):
        return f"{self.action}: {self.resource_type} {self.resource_id}"
