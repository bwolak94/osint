"""add performance indexes for common query patterns

Revision ID: 20260423000000
Revises: p6q7r8s9t0u1
Create Date: 2026-04-23 00:00:00.000000

"""
from alembic import op

# revision identifiers
revision = '20260423000000'
down_revision = 'p6q7r8s9t0u1'


def upgrade() -> None:
    # Investigations table
    op.create_index('ix_investigations_status', 'investigations', ['status'])
    op.create_index('ix_investigations_created_at', 'investigations', ['created_at'])
    op.create_index('ix_investigations_user_id', 'investigations', ['user_id'])

    # Scan results
    op.create_index('ix_scan_results_investigation_id', 'scan_results', ['investigation_id'])
    op.create_index('ix_scan_results_created_at', 'scan_results', ['created_at'])
    op.create_index('ix_scan_results_scanner_type', 'scan_results', ['scanner_type'])
    op.create_index('ix_scan_results_status', 'scan_results', ['status'])

    # Entities
    op.create_index('ix_entities_investigation_id', 'entities', ['investigation_id'])
    op.create_index('ix_entities_entity_type', 'entities', ['entity_type'])

    # Annotations
    op.create_index('ix_annotations_investigation_id', 'annotations', ['investigation_id'])
    op.create_index('ix_annotations_target_id', 'annotations', ['target_id'])


def downgrade() -> None:
    op.drop_index('ix_investigations_status')
    op.drop_index('ix_investigations_created_at')
    op.drop_index('ix_investigations_user_id')
    op.drop_index('ix_scan_results_investigation_id')
    op.drop_index('ix_scan_results_created_at')
    op.drop_index('ix_scan_results_scanner_type')
    op.drop_index('ix_scan_results_status')
    op.drop_index('ix_entities_investigation_id')
    op.drop_index('ix_entities_entity_type')
    op.drop_index('ix_annotations_investigation_id')
    op.drop_index('ix_annotations_target_id')
