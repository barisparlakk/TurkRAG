"""Add dashboard collections and UI settings.

Revision ID: 0005_dashboard_ops
Revises: 0004_platform_admin_role
Create Date: 2026-06-29
"""

from alembic import op

revision = "0005_dashboard_ops"
down_revision = "0004_platform_admin_role"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS collections (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            description TEXT,
            color TEXT NOT NULL DEFAULT '#4f8cff',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(tenant_id, name)
        );

        ALTER TABLE documents
            ADD COLUMN IF NOT EXISTS collection_id UUID REFERENCES collections(id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS file_type TEXT,
            ADD COLUMN IF NOT EXISTS size_bytes BIGINT;

        CREATE TABLE IF NOT EXISTS tenant_ui_settings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL,
            settings_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(tenant_id, user_id)
        );

        CREATE INDEX IF NOT EXISTS idx_collections_tenant ON collections(tenant_id);
        CREATE INDEX IF NOT EXISTS idx_documents_collection ON documents(collection_id);
        CREATE INDEX IF NOT EXISTS idx_tenant_ui_settings_tenant_user
            ON tenant_ui_settings(tenant_id, user_id);
    """)


def downgrade() -> None:
    op.execute("""
        DROP INDEX IF EXISTS idx_tenant_ui_settings_tenant_user;
        DROP INDEX IF EXISTS idx_documents_collection;
        DROP INDEX IF EXISTS idx_collections_tenant;
        DROP TABLE IF EXISTS tenant_ui_settings;
        ALTER TABLE documents
            DROP COLUMN IF EXISTS size_bytes,
            DROP COLUMN IF EXISTS file_type,
            DROP COLUMN IF EXISTS collection_id;
        DROP TABLE IF EXISTS collections;
    """)
