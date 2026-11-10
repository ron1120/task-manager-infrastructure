# The audit log: an append-only record of who did what. Callers add the entry in the same database transaction
# as the change itself, so an action and its audit entry are saved together or not at all.
from sqlalchemy.orm import Session

from app.core.actor import Actor
from app.models import AuditLog


def record(
    db: Session,
    actor: Actor,
    action: str,
    entity_type: str,
    entity_id: int | str | None = None,
    details: dict | None = None,
    ip: str | None = None,
) -> None:
    # Never put secrets (passwords, API keys, tokens) in `details`.
    db.add(
        AuditLog(
            actor=actor.label,
            actor_type=actor.kind,
            action=action,
            entity_type=entity_type,
            entity_id=None if entity_id is None else str(entity_id),
            details=details,
            ip=ip,
        )
    )
