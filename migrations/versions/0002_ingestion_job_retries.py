"""Add ingestion job retry metadata.

Revision ID: 0002_ingestion_job_retries
Revises: 0001_baseline
Create Date: 2026-06-16
"""

from alembic import op

revision = "0002_ingestion_job_retries"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE ingestion_jobs
            ADD COLUMN IF NOT EXISTS attempts INT NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS max_attempts INT NOT NULL DEFAULT 3,
            ADD COLUMN IF NOT EXISTS last_heartbeat_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS retry_after TIMESTAMPTZ;

        CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_runnable
            ON ingestion_jobs(status, retry_after, created_at);

        CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_heartbeat
            ON ingestion_jobs(status, last_heartbeat_at, started_at);
    """)


def downgrade() -> None:
    op.execute("""
        DROP INDEX IF EXISTS idx_ingestion_jobs_heartbeat;
        DROP INDEX IF EXISTS idx_ingestion_jobs_runnable;

        ALTER TABLE ingestion_jobs
            DROP COLUMN IF EXISTS retry_after,
            DROP COLUMN IF EXISTS last_heartbeat_at,
            DROP COLUMN IF EXISTS max_attempts,
            DROP COLUMN IF EXISTS attempts;
    """)
