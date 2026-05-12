"""Improvements: JSONB columns, constraints, ACL, quota, risk score tables.

Revision ID: 20260425100000
Revises: 20260424140000
Create Date: 2026-04-25 10:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "20260425100000"
down_revision = "20260424140000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Convert JSON columns to JSONB ───────────────────────────────────

    # investigations.seed_inputs
    op.alter_column(
        "investigations",
        "seed_inputs",
        type_=JSONB,
        postgresql_using="seed_inputs::jsonb",
        existing_nullable=False,
    )

    # identities.metadata
    op.alter_column(
        "identities",
        "metadata",
        type_=JSONB,
        postgresql_using="metadata::jsonb",
        existing_nullable=False,
    )

    # scan_results.raw_data
    op.alter_column(
        "scan_results",
        "raw_data",
        type_=JSONB,
        postgresql_using="raw_data::jsonb",
        existing_nullable=False,
    )

    # ── 2. Add updated_at to scan_results ──────────────────────────────────
    op.add_column(
        "scan_results",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # ── 3. Add confidence_score CHECK constraint ────────────────────────────
    op.create_check_constraint(
        "ck_identities_confidence_range",
        "identities",
        "confidence_score BETWEEN 0.0 AND 1.0",
    )

    # ── 4. Add partial index on users(email) WHERE is_active = true ────────
    op.create_index(
        "ix_users_active_email",
        "users",
        ["email"],
        postgresql_where=sa.text("is_active = true"),
    )

    # ── 5. Create investigation_acl table ──────────────────────────────────
    op.create_table(
        "investigation_acl",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("investigation_id", UUID(as_uuid=True), sa.ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("permission", sa.String(16), nullable=False),
        sa.Column("granted_by", UUID(as_uuid=True), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("permission IN ('view', 'edit', 'admin')", name="ck_acl_permission_values"),
    )
    op.create_index("ix_acl_inv_user", "investigation_acl", ["investigation_id", "user_id"], unique=True)

    # ── 6. Create investigation_risk_scores table ──────────────────────────
    op.create_table(
        "investigation_risk_scores",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("investigation_id", UUID(as_uuid=True), sa.ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("breach_count", sa.Integer(), default=0, nullable=False),
        sa.Column("exposed_services", sa.Integer(), default=0, nullable=False),
        sa.Column("avg_confidence", sa.Float(), default=0.0, nullable=False),
        sa.Column("factors", JSONB, default=dict, nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("score BETWEEN 0.0 AND 100.0", name="ck_risk_score_range"),
    )

    # ── 7. Create scanner_quotas table ────────────────────────────────────
    op.create_table(
        "scanner_quotas",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", sa.String(100), nullable=False),
        sa.Column("scanner_name", sa.String(100), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requests_used", sa.Integer(), default=0, nullable=False),
        sa.Column("requests_limit", sa.Integer(), default=1000, nullable=False),
        sa.Column("last_request_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_scanner_quotas_ws_scanner", "scanner_quotas", ["workspace_id", "scanner_name"])


def downgrade() -> None:
    op.drop_table("scanner_quotas")
    op.drop_table("investigation_risk_scores")
    op.drop_table("investigation_acl")
    op.drop_index("ix_users_active_email", "users")
    op.drop_constraint("ck_identities_confidence_range", "identities", type_="check")
    op.drop_column("scan_results", "updated_at")

    # Revert JSONB → JSON (lossy only in edge cases — JSONB is a superset)
    op.alter_column("scan_results", "raw_data", type_=sa.JSON, existing_nullable=False)
    op.alter_column("identities", "metadata", type_=sa.JSON, existing_nullable=False)
    op.alter_column("investigations", "seed_inputs", type_=sa.JSON, existing_nullable=False)
