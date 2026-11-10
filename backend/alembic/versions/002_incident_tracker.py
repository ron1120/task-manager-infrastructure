"""incident tracker: roles, incidents, timeline, audit log, API keys

Revision ID: 002
Revises: 001
Create Date: 2026-11-08 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOW = sa.text("now()")


def upgrade() -> None:
    # Existing accounts become analysts; the oldest one becomes the admin so someone can manage keys and roles.
    op.add_column("users", sa.Column("role", sa.String(length=20), server_default="analyst", nullable=False))
    op.execute("UPDATE users SET role = 'admin' WHERE id = (SELECT MIN(id) FROM users)")

    op.create_table(
        "incidents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(length=2), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("service", sa.String(length=100), nullable=True),
        sa.Column("environment", sa.String(length=50), nullable=True),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("occurrences", sa.Integer(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("assignee_id", sa.Integer(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "external_id", name="uq_incident_source_external"),
    )
    op.create_index(op.f("ix_incidents_id"), "incidents", ["id"], unique=False)
    op.create_index(op.f("ix_incidents_severity"), "incidents", ["severity"], unique=False)
    op.create_index(op.f("ix_incidents_status"), "incidents", ["status"], unique=False)
    op.create_index(op.f("ix_incidents_service"), "incidents", ["service"], unique=False)

    op.create_table(
        "incident_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_incident_events_incident_id"), "incident_events", ["incident_id"], unique=False)

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.String(length=50), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_log_created_at"), "audit_log", ["created_at"], unique=False)
    op.create_index(op.f("ix_audit_log_actor"), "audit_log", ["actor"], unique=False)
    op.create_index(op.f("ix_audit_log_action"), "audit_log", ["action"], unique=False)

    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("prefix", sa.String(length=12), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
    )


def downgrade() -> None:
    op.drop_table("api_keys")
    for name in ("ix_audit_log_action", "ix_audit_log_actor", "ix_audit_log_created_at"):
        op.drop_index(op.f(name), table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index(op.f("ix_incident_events_incident_id"), table_name="incident_events")
    op.drop_table("incident_events")
    for name in ("ix_incidents_service", "ix_incidents_status", "ix_incidents_severity", "ix_incidents_id"):
        op.drop_index(op.f(name), table_name="incidents")
    op.drop_table("incidents")
    op.drop_column("users", "role")
