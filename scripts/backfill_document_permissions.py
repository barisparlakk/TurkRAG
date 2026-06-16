"""Backfill document ACL rows for legacy documents.

This is safe to run repeatedly. It grants tenant admins owner access and active
members viewer access only for documents that currently have no ACL rows.
"""

import argparse
import logging
import os

logger = logging.getLogger(__name__)

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://turkrag:turkrag_secret@localhost/turkrag")

BACKFILL_SQL = """
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
    ON CONFLICT (document_id, user_id) DO NOTHING
"""

DRY_RUN_SQL = """
    SELECT COUNT(*)
    FROM documents d
    JOIN users u
      ON u.tenant_id = d.tenant_id
     AND u.is_active = true
    WHERE NOT EXISTS (
        SELECT 1
        FROM document_permissions existing
        WHERE existing.document_id = d.id
    )
"""

SKIPPED_DOCUMENTS_SQL = """
    SELECT COUNT(*)
    FROM documents d
    WHERE NOT EXISTS (
        SELECT 1
        FROM document_permissions existing
        WHERE existing.document_id = d.id
    )
      AND NOT EXISTS (
        SELECT 1
        FROM users u
        WHERE u.tenant_id = d.tenant_id
          AND u.is_active = true
    )
"""


def backfill_document_permissions(conn, *, dry_run: bool = False) -> dict[str, int]:
    """Backfill missing ACLs and return a concise summary."""
    with conn.cursor() as cur:
        cur.execute(DRY_RUN_SQL)
        candidate_rows = int(cur.fetchone()[0])

        cur.execute(SKIPPED_DOCUMENTS_SQL)
        skipped_documents = int(cur.fetchone()[0])

        inserted_rows = 0
        if not dry_run:
            cur.execute(BACKFILL_SQL)
            inserted_rows = cur.rowcount

    if dry_run:
        conn.rollback()
    else:
        conn.commit()

    return {
        "candidate_rows": candidate_rows,
        "inserted_rows": inserted_rows,
        "skipped_documents_without_active_users": skipped_documents,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill legacy document permission ACLs")
    parser.add_argument("--dry-run", action="store_true", help="Show candidate row counts without writing")
    args = parser.parse_args()

    import psycopg2

    conn = psycopg2.connect(POSTGRES_URL)
    try:
        summary = backfill_document_permissions(conn, dry_run=args.dry_run)
    finally:
        conn.close()

    print(
        "Document permission backfill: "
        f"candidates={summary['candidate_rows']} "
        f"inserted={summary['inserted_rows']} "
        f"skipped_without_active_users={summary['skipped_documents_without_active_users']}"
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()
