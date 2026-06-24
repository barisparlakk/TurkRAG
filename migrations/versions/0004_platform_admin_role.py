"""Allow global platform administrator role.

Revision ID: 0004_platform_admin_role
Revises: 0003_acl_backfill
Create Date: 2026-06-24
"""

from alembic import op

revision = "0004_platform_admin_role"
down_revision = "0003_acl_backfill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
        ALTER TABLE users
            ADD CONSTRAINT users_role_check
            CHECK (role IN ('platform_admin', 'admin', 'member'));
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
        ALTER TABLE users
            ADD CONSTRAINT users_role_check
            CHECK (role IN ('admin', 'member'));
    """)
