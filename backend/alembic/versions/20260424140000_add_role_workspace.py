"""add role + workspace tables

Revision ID: 20260424140000
Revises: 20260424120000
Create Date: 2026-04-24 14:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260424140000"
down_revision = "20260424120000"
branch_labels = None
depends_on = None


def _table_exists(conn, table_name: str) -> bool:
    return bool(conn.execute(
        sa.text("SELECT 1 FROM information_schema.tables WHERE table_name=:t"),
        {"t": table_name},
    ).fetchone())


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    return bool(conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name=:t AND column_name=:c"
        ),
        {"t": table_name, "c": column_name},
    ).fetchone())


def upgrade() -> None:
    conn = op.get_bind()

    # --- Add role column to users (idempotent) --------------------------------
    if not _column_exists(conn, "users", "role"):
        op.add_column(
            "users",
            sa.Column("role", sa.String(length=32), nullable=False, server_default="viewer"),
        )

    # --- Workspace table (idempotent) -----------------------------------------
    if not _table_exists(conn, "workspaces"):
        op.create_table(
            "workspaces",
            sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("slug", sa.String(length=128), nullable=False, unique=True),
            sa.Column("owner_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("settings", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_workspaces_owner_id", "workspaces", ["owner_id"])

    # --- Workspace membership (idempotent) ------------------------------------
    if not _table_exists(conn, "workspace_members"):
        op.create_table(
            "workspace_members",
            sa.Column("workspace_id", sa.UUID(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False, server_default="viewer"),
            sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("workspace_id", "user_id"),
        )

    # --- workspace_id FK on investigations (idempotent) -----------------------
    if not _column_exists(conn, "investigations", "workspace_id"):
        op.add_column(
            "investigations",
            sa.Column("workspace_id", sa.UUID(), sa.ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True),
        )
        op.create_index("ix_investigations_workspace_id", "investigations", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_investigations_workspace_id", table_name="investigations")
    op.drop_column("investigations", "workspace_id")
    op.drop_table("workspace_members")
    op.drop_index("ix_workspaces_owner_id", table_name="workspaces")
    op.drop_table("workspaces")
    op.drop_column("users", "role")
