"""Append-only audit trail helper."""

from sqlalchemy.orm import Session

from app.models import AuditLog


def log_action(
    db: Session,
    user_id: int,
    action: str,
    resource_type: str | None = None,
    resource_id: int | None = None,
    details: dict | None = None,
) -> AuditLog:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
    )
    db.add(entry)
    return entry
