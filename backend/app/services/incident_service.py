# Business logic for incidents: create, change status, comment, assign, search and summarise.
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.actor import Actor
from app.models import SLA_HOURS, TRANSITIONS, Incident, IncidentEvent, User
from app.services import audit


class InvalidTransition(ValueError):
    pass


class UnknownUser(ValueError):
    pass


def now() -> datetime:
    return datetime.now(timezone.utc)


def aware(value: datetime | None) -> datetime | None:
    # SQLite (used in tests) hands back naive datetimes; Postgres hands back aware ones. Treat naive as UTC.
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def sla_due(created_at: datetime, severity: str) -> datetime:
    return created_at + timedelta(hours=SLA_HOURS[severity])


def is_breached(incident: Incident, at: datetime | None = None) -> bool:
    return incident.status != "resolved" and (at or now()) > aware(incident.sla_due_at)


def _event(db: Session, incident: Incident, kind: str, actor: Actor, body: str) -> None:
    db.add(IncidentEvent(incident=incident, kind=kind, actor=actor.label, body=body))


def _assignee(db: Session, assignee_id: int | None) -> User | None:
    if assignee_id is None:
        return None
    user = db.query(User).filter(User.id == assignee_id).first()
    if user is None:
        raise UnknownUser(f"No user with id {assignee_id}")
    return user


def create_incident(
    db: Session,
    actor: Actor,
    *,
    title: str,
    severity: str = "P3",
    description: str | None = None,
    service: str | None = None,
    environment: str | None = None,
    source: str = "manual",
    external_id: str | None = None,
    evidence: dict | None = None,
    assignee_id: int | None = None,
    ip: str | None = None,
) -> Incident:
    assignee = _assignee(db, assignee_id)
    opened = now()
    incident = Incident(
        title=title,
        description=description,
        severity=severity,
        status="open",
        service=service,
        environment=environment,
        source=source,
        external_id=external_id,
        evidence=evidence,
        assignee_id=assignee.id if assignee else None,
        created_by_id=actor.user_id,
        created_at=opened,
        sla_due_at=sla_due(opened, severity),
    )
    db.add(incident)
    db.flush()  # assigns incident.id so the event and audit entry can refer to it
    _event(db, incident, "system", actor, f"Opened as {severity} by {actor.label} (source: {source}).")
    if assignee:
        _event(db, incident, "assignment", actor, f"Assigned to {assignee.email}.")
    audit.record(
        db, actor, "incident.create", "incident", incident.id,
        {"severity": severity, "source": source, "service": service}, ip,
    )
    db.commit()
    db.refresh(incident)
    return incident


def get_incident(db: Session, incident_id: int) -> Incident | None:
    return db.query(Incident).filter(Incident.id == incident_id).first()


def list_incidents(
    db: Session,
    *,
    status: str | None = None,
    severity: str | None = None,
    service: str | None = None,
    environment: str | None = None,
    source: str | None = None,
    assignee_id: int | None = None,
    unassigned: bool = False,
    q: str | None = None,
    breached: bool | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[Incident], int]:
    query = db.query(Incident)
    if status:
        query = query.filter(Incident.status == status)
    if severity:
        query = query.filter(Incident.severity == severity)
    if service:
        query = query.filter(Incident.service == service)
    if environment:
        query = query.filter(Incident.environment == environment)
    if source:
        query = query.filter(Incident.source == source)
    if assignee_id is not None:
        query = query.filter(Incident.assignee_id == assignee_id)
    if unassigned:
        query = query.filter(Incident.assignee_id.is_(None))
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Incident.title.ilike(like), Incident.description.ilike(like), Incident.service.ilike(like)))
    if breached is not None:
        overdue = (Incident.status != "resolved") & (Incident.sla_due_at < now())
        query = query.filter(overdue if breached else ~overdue)
    total = query.count()
    # Most severe first (P1 sorts before P4), then newest.
    items = query.order_by(Incident.severity, Incident.created_at.desc(), Incident.id.desc()).offset(offset).limit(limit).all()
    return items, total


def change_status(
    db: Session, incident: Incident, actor: Actor, new_status: str, note: str | None = None, ip: str | None = None
) -> Incident:
    old = incident.status
    if new_status not in TRANSITIONS[old]:
        allowed = ", ".join(sorted(TRANSITIONS[old]))
        raise InvalidTransition(f"Cannot move an incident from {old} to {new_status}. Allowed: {allowed}.")
    at = now()
    incident.status = new_status
    if old == "open" and incident.acknowledged_at is None:
        incident.acknowledged_at = at  # the first step out of "open" is the acknowledgement
    if new_status == "resolved":
        incident.resolved_at = at
    elif old == "resolved":
        incident.resolved_at = None  # reopened
    body = f"Status changed from {old} to {new_status} by {actor.label}."
    _event(db, incident, "status", actor, body + (f" Note: {note}" if note else ""))
    audit.record(db, actor, "incident.status_change", "incident", incident.id, {"from": old, "to": new_status}, ip)
    db.commit()
    db.refresh(incident)
    return incident


def add_comment(db: Session, incident: Incident, actor: Actor, body: str, ip: str | None = None) -> Incident:
    _event(db, incident, "comment", actor, body)
    audit.record(db, actor, "incident.comment", "incident", incident.id, None, ip)
    db.commit()
    db.refresh(incident)
    return incident


def update_incident(
    db: Session, incident: Incident, actor: Actor, changes: dict, ip: str | None = None
) -> Incident:
    """Apply the fields in `changes` (only the ones the caller sent) and log each real change on the timeline."""
    changed: dict[str, dict] = {}
    for field in ("title", "description", "service", "environment"):
        if field in changes and changes[field] != getattr(incident, field):
            changed[field] = {"from": getattr(incident, field), "to": changes[field]}
            setattr(incident, field, changes[field])
    if "severity" in changes and changes["severity"] is not None and changes["severity"] != incident.severity:
        old = incident.severity
        incident.severity = changes["severity"]
        # The deadline follows the new severity, counted from when the incident was opened.
        incident.sla_due_at = sla_due(aware(incident.created_at), incident.severity)
        changed["severity"] = {"from": old, "to": incident.severity}
        _event(db, incident, "severity", actor, f"Severity changed from {old} to {incident.severity} by {actor.label}.")
    if "assignee_id" in changes and changes["assignee_id"] != incident.assignee_id:
        assignee = _assignee(db, changes["assignee_id"])
        changed["assignee_id"] = {"from": incident.assignee_id, "to": changes["assignee_id"]}
        incident.assignee_id = assignee.id if assignee else None
        _event(
            db, incident, "assignment", actor,
            f"Assigned to {assignee.email} by {actor.label}." if assignee else f"Unassigned by {actor.label}.",
        )
    if changed:
        audit.record(db, actor, "incident.update", "incident", incident.id, {"changed": list(changed)}, ip)
        db.commit()
        db.refresh(incident)
    return incident


def stats(db: Session) -> dict:
    at = now()
    since = at - timedelta(days=30)
    rows = db.query(Incident).all()
    open_rows = [i for i in rows if i.status != "resolved"]
    by_severity = {s: 0 for s in ("P1", "P2", "P3", "P4")}
    for i in open_rows:
        by_severity[i.severity] += 1

    def mean_hours(pairs: list[tuple[datetime, datetime]]) -> float | None:
        if not pairs:
            return None
        return round(sum((aware(end) - aware(start)).total_seconds() for start, end in pairs) / len(pairs) / 3600, 2)

    acked = [(i.created_at, i.acknowledged_at) for i in rows if i.acknowledged_at and aware(i.created_at) >= since]
    resolved = [(i.created_at, i.resolved_at) for i in rows if i.resolved_at and aware(i.resolved_at) >= since]
    return {
        "open_total": len(open_rows),
        "open_by_severity": by_severity,
        "breached": sum(1 for i in open_rows if is_breached(i, at)),
        "unassigned": sum(1 for i in open_rows if i.assignee_id is None),
        "mtta_hours": mean_hours(acked),
        "mttr_hours": mean_hours(resolved),
    }
