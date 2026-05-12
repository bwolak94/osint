"""Add rag_chunks table with pgvector HNSW index and pg_trgm GIN index.

Revision ID: l2m3n4o5p6q7
Revises: j0k1l2m3n4o5
Create Date: 2026-04-22 02:00:00.000000

Purpose:
  Creates the rag_chunks table used by the RAG knowledge base pipeline
  (Task 013).  Stores embedded CVE/OWASP/CISA-KEV text chunks with
  per-tenant isolation support.

Affected tables:
  - rag_chunks (CREATE)

Extensions required (must already exist):
  - vector  (pgvector)
  - pg_trgm (trigram text search)

Special considerations:
  - The HNSW index parameters (m=16, ef_construction=64) are conservative
    defaults suitable for up to ~1M rows.  Increase ef_construction for
    higher recall at the cost of build time.
  - The ON CONFLICT target used by the ingestion worker requires the
    unique index on (source, source_id).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "l2m3n4o5p6q7"
down_revision = "j0k1l2m3n4o5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Check if pgvector is available WITHOUT running DDL that could abort the transaction.
    # We query pg_available_extensions — a read-only view, safe inside a transaction.
    result = conn.execute(sa.text(
        "SELECT count(*) FROM pg_available_extensions WHERE name = 'vector'"
    ))
    has_vector = result.scalar() > 0

    if has_vector:
        conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))

    # Enable pg_trgm if available (safe read-only check first)
    result2 = conn.execute(sa.text(
        "SELECT count(*) FROM pg_available_extensions WHERE name = 'pg_trgm'"
    ))
    has_trgm = result2.scalar() > 0
    if has_trgm:
        conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))

    # Primary table — embedding column is TEXT when pgvector missing, vector(1024) when present
    embedding_col = (
        sa.Column("embedding", sa.Text(), nullable=True,
                  comment="pgvector vector(1024) — cast to ::vector at query time")
    )
    op.create_table(
        "rag_chunks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        embedding_col,
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    if has_vector:
        # Alter the embedding column to the actual vector type
        conn.execute(sa.text(
            "ALTER TABLE rag_chunks ALTER COLUMN embedding TYPE vector(1024) "
            "USING embedding::vector(1024)"
        ))

    # Unique constraint for ON CONFLICT upsert
    op.create_index(
        "uq_rag_chunks_source_source_id",
        "rag_chunks",
        ["source", "source_id"],
        unique=True,
        postgresql_where=sa.text("source_id IS NOT NULL"),
    )

    if has_vector:
        # HNSW vector index for cosine similarity search
        conn.execute(sa.text(
            "CREATE INDEX rag_hnsw_idx ON rag_chunks "
            "USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)"
        ))

    # GIN trigram index for keyword search
    try:
        conn.execute(sa.text(
            "CREATE INDEX rag_trgm_idx ON rag_chunks USING gin (content gin_trgm_ops)"
        ))
    except Exception:
        pass  # pg_trgm not available

    # Composite index for tenant + source filtering
    op.create_index(
        "rag_source_tenant_idx",
        "rag_chunks",
        ["tenant_id", "source"],
    )


def downgrade() -> None:
    # Drop indexes first, then the table.
    # NOTE: dropping vector/pg_trgm extensions is intentionally omitted —
    # other tables may depend on them.
    op.execute("DROP INDEX IF EXISTS rag_hnsw_idx")
    op.execute("DROP INDEX IF EXISTS rag_trgm_idx")
    op.drop_index("rag_source_tenant_idx", table_name="rag_chunks")
    op.drop_index("uq_rag_chunks_source_source_id", table_name="rag_chunks")
    op.drop_table("rag_chunks")
