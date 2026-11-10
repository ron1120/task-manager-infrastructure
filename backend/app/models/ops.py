# Incident tracker tables: incidents + their timeline, the audit log and API keys for machine callers
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

# Allowed values. They are stored as plain strings and validated in the API layer.
ROLES = ("viewer", "analyst", "admin")
SEVERITIES = ("P1", "P2", "P3", "P4")
STATUSES = ("open", "triaged", "mitigated", "resolved")
SOURCES = ("manual", "github_actions", "alertmanager", "ci_triage", "generic")

# Hours allowed to resolve an incident, by severity. sla_due_at = created_at + this.
SLA_HOURS = {"P1": 4, "P2": 24, "P3": 72, "P4": 168}

# Which status may follow which. A resolved incident can only be reopened.
TRANSITIONS = {
    "open": {"triaged", "resolved"},
    "triaged": {"open", "mitigated", "resolved"},
    "mitigated": {"triaged", "resolved"},
    "resolved": {"open"},
}


class Incident(Base):
    __tablename__ = "incidents"
    # The same machine event delivered twice (same source + id) is one incident, not two.
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_incident_source_external"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    service: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    environment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    occurrences: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # how many times it was reported
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # raw facts from the machine that opened it

    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    sla_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    assignee = relationship("User", foreign_keys=[assignee_id])
    events: Mapped[list["IncidentEvent"]] = relationship(
        "IncidentEvent",
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="IncidentEvent.created_at, IncidentEvent.id",
    )


class IncidentEvent(Base):
    """One line of an incident's timeline: a comment, a status change, an assignment or a system note."""

    __tablename__ = "incident_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # comment | status | assignment | severity | system
    actor: Mapped[str] = mapped_column(String(255), nullable=False)  # "user:a@b.com", "key:github-ci" or "system"
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    incident: Mapped["Incident"] = relationship("Incident", back_populates="events")


class AuditLog(Base):
    """Append-only record of who did what. The API only ever inserts and reads this table."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    actor: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)  # user | api_key | system | anonymous
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # e.g. incident.status_change
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ApiKey(Base):
    """A credential for a machine (CI, Alertmanager) to report incidents. Only a hash of the key is stored."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)  # the one intake endpoint this key may use
    prefix: Mapped[str] = mapped_column(String(12), nullable=False)  # first characters, so keys can be told apart
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)  # sha256 of the full key
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
