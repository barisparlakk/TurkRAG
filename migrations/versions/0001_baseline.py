"""Baseline TurkRAG schema.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-06-16
"""

from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("""
        CREATE TABLE IF NOT EXISTS tenants (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL UNIQUE,
            slug TEXT NOT NULL UNIQUE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS documents (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
            filename TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            chunk_count INTEGER,
            status TEXT DEFAULT 'processing',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            version INT DEFAULT 1,
            parent_id UUID REFERENCES documents(id)
        );

        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
            email TEXT NOT NULL,
            password_hash TEXT,
            role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('admin', 'member')),
            is_active BOOLEAN NOT NULL DEFAULT true,
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL DEFAULT 'anonymous',
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            citations JSONB DEFAULT '[]',
            feedback SMALLINT DEFAULT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS query_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
            query TEXT NOT NULL,
            answer_length INT,
            num_citations INT,
            query_time_ms INT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS document_permissions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL,
            permission_level TEXT NOT NULL CHECK (permission_level IN ('viewer', 'editor', 'owner')),
            granted_by TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(document_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS eval_runs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            run_label TEXT,
            config_json JSONB,
            metrics_json JSONB,
            per_query_json JSONB,
            num_queries INT,
            avg_score NUMERIC(5,4),
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS ingestion_jobs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
            filename TEXT NOT NULL,
            file_path TEXT,
            status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
            error_message TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ
        );

        CREATE TABLE IF NOT EXISTS document_versions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            version INT NOT NULL DEFAULT 1,
            filename TEXT NOT NULL,
            chunk_count INT,
            is_current BOOLEAN DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_sessions_tenant ON sessions(tenant_id);
        CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
        CREATE INDEX IF NOT EXISTS idx_query_logs_tenant ON query_logs(tenant_id);
        CREATE INDEX IF NOT EXISTS idx_documents_tenant ON documents(tenant_id);
        CREATE INDEX IF NOT EXISTS idx_doc_permissions_user ON document_permissions(user_id);
        CREATE INDEX IF NOT EXISTS idx_doc_permissions_doc ON document_permissions(document_id);
        CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_status ON ingestion_jobs(status);
        CREATE INDEX IF NOT EXISTS idx_eval_runs_tenant ON eval_runs(tenant_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_tenant_email_lower
            ON users (tenant_id, lower(email));
    """)


def downgrade() -> None:
    op.execute("""
        DROP TABLE IF EXISTS document_versions CASCADE;
        DROP TABLE IF EXISTS ingestion_jobs CASCADE;
        DROP TABLE IF EXISTS eval_runs CASCADE;
        DROP TABLE IF EXISTS document_permissions CASCADE;
        DROP TABLE IF EXISTS query_logs CASCADE;
        DROP TABLE IF EXISTS messages CASCADE;
        DROP TABLE IF EXISTS sessions CASCADE;
        DROP TABLE IF EXISTS users CASCADE;
        DROP TABLE IF EXISTS documents CASCADE;
        DROP TABLE IF EXISTS tenants CASCADE;
    """)
