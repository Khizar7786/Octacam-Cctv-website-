from .models import AuditEvent


def record_audit_event(*, actor, resource_type, resource_id, action, before_data, after_data, metadata=None):
    return AuditEvent.objects.create(
        actor=actor,
        resource_type=resource_type,
        resource_id=str(resource_id),
        action=action,
        before_data=before_data,
        after_data=after_data,
        metadata=metadata or {},
    )
