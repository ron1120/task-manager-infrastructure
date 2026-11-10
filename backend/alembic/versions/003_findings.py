"""security findings and scans

Revision ID: 003
Revises: 002
Create Date: 2026-11-10 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOW = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "scans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scanner", sa.String(length=30), nullable=False),
        sa.Column("target", sa.String(length=255), nullable=False),
        sa.Column("ref", sa.String(length=100), nullable=True),
        sa.Column("run_url", sa.String(length=500), nullable=True),
        sa.Column("complete", sa.Boolean(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("new_count", sa.Integer(), nullable=False),
        sa.Column("fixed_count", sa.Integer(), nullable=False),
        sa.Column("by_severity", sa.JSON(), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_scans_scanner"), "scans", ["scanner"], unique=False)

    op.create_table(
        "findings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(length=40), nullable=False),
        sa.Column("scanner", sa.String(length=30), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("target", sa.String(length=255), nullable=False),
        sa.Column("rule_id", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(length=10), nullable=False),
        sa.Column("package", sa.String(length=200), nullable=True),
        sa.Column("installed_version", sa.String(length=100), nullable=True),
        sa.Column("fixed_version", sa.String(length=200), nullable=True),
        sa.Column("location", sa.String(length=500), nullable=True),
        sa.Column("url", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("status_reason", sa.Text(), nullable=True),
        sa.Column("status_by", sa.String(length=255), nullable=True),
        sa.Column("occurrences", sa.Integer(), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fixed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scanner", "target", "fingerprint", name="uq_finding_identity"),
    )
    for column in ("id", "scanner", "target", "rule_id", "severity", "status"):
        op.create_index(op.f(f"ix_findings_{column}"), "findings", [column], unique=False)


def downgrade() -> None:
    for column in ("status", "severity", "rule_id", "target", "scanner", "id"):
        op.drop_index(op.f(f"ix_findings_{column}"), table_name="findings")
    op.drop_table("findings")
    op.drop_index(op.f("ix_scans_scanner"), table_name="scans")
    op.drop_table("scans")
