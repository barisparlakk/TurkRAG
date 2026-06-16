"""Backfill ACL rows for legacy documents.

Revision ID: 0003_backfill_document_permissions
Revises: 0002_ingestion_job_retries
Create Date: 2026-06-16
"""

from alembic import op

revision = "0003_backfill_document_permissions"
down_revision = "0002_ingestion_job_retries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO document_permissions (document_id, user_id, permission_level, granted_by)
        SELECT
            d.id,
            u.id::TEXT,
            CASE WHEN u.role = 'admin' THEN 'owner' ELSE 'viewer' END,
            NULL
        FROM documents d
        JOIN users u
          ON u.tenant_id = d.tenant_id
         AND u.is_active = true
        WHERE NOT EXISTS (
            SELECT 1
            FROM document_permissions existing
            WHERE existing.document_id = d.id
        )
        ON CONFLICT (document_id, user_id) DO NOTHING;
    """)


def downgrade() -> None:
    # Data backfill only. Do not remove explicit ACL rows on downgrade.
    pass
