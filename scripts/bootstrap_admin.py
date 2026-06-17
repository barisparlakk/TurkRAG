"""Bootstrap or recover the first admin user for an existing tenant.

This is intended for existing deployments that already have tenant rows but
need a one-time local email/password admin before development auth is disabled.
The command is idempotent: it creates the admin user if missing, otherwise it
promotes/reactivates the existing tenant user and rotates the password hash.
"""

import argparse
import logging
import os

from api.auth import hash_password

logger = logging.getLogger(__name__)

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://turkrag:turkrag_secret@localhost/turkrag")


def bootstrap_admin_user(
    conn,
    *,
    tenant_slug: str,
    email: str,
    password: str,
    dry_run: bool = False,
) -> dict[str, str | bool]:
    """Create or repair a tenant admin account and return a concise summary."""
    normalized_slug = tenant_slug.strip()
    normalized_email = email.strip().lower()

    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, name, slug FROM tenants WHERE slug=%s",
            (normalized_slug,),
        )
        tenant_row = cur.fetchone()
        if not tenant_row:
            raise ValueError(f"Tenant slug '{normalized_slug}' was not found.")

        tenant_id = str(tenant_row[0])
        cur.execute(
            """SELECT id, role, is_active
               FROM users
               WHERE tenant_id=%s AND lower(email)=lower(%s)""",
            (tenant_id, normalized_email),
        )
        user_row = cur.fetchone()

        if user_row:
            user_id = str(user_row[0])
            previous_role = user_row[1]
            previous_active = bool(user_row[2])
            action = "unchanged" if previous_role == "admin" and previous_active else "updated"
            if not dry_run:
                cur.execute(
                    """UPDATE users
                       SET password_hash=%s,
                           role='admin',
                           is_active=true,
                           updated_at=NOW()
                       WHERE id=%s""",
                    (hash_password(password), user_id),
                )
        else:
            action = "created"
            user_id = ""
            previous_role = None
            previous_active = False
            if not dry_run:
                cur.execute(
                    """INSERT INTO users (tenant_id, email, password_hash, role, is_active)
                       VALUES (%s, %s, %s, 'admin', true)
                       RETURNING id""",
                    (tenant_id, normalized_email, hash_password(password)),
                )
                inserted = cur.fetchone()
                user_id = str(inserted[0])

    if dry_run:
        conn.rollback()
    else:
        conn.commit()

    return {
        "tenant_id": tenant_id,
        "tenant_name": tenant_row[1],
        "tenant_slug": tenant_row[2],
        "email": normalized_email,
        "user_id": user_id,
        "action": action,
        "dry_run": dry_run,
        "was_active": previous_active,
        "previous_role": previous_role or "missing",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap or recover a tenant admin user")
    parser.add_argument("--tenant-slug", required=True, help="Existing tenant slug")
    parser.add_argument("--email", required=True, help="Admin email")
    parser.add_argument("--password", required=True, help="Admin password")
    parser.add_argument("--dry-run", action="store_true", help="Validate the action without writing changes")
    args = parser.parse_args()

    import psycopg2

    conn = psycopg2.connect(POSTGRES_URL)
    try:
        summary = bootstrap_admin_user(
            conn,
            tenant_slug=args.tenant_slug,
            email=args.email,
            password=args.password,
            dry_run=args.dry_run,
        )
    finally:
        conn.close()

    print(
        "Admin bootstrap: "
        f"tenant={summary['tenant_slug']} "
        f"email={summary['email']} "
        f"action={summary['action']} "
        f"previous_role={summary['previous_role']} "
        f"was_active={summary['was_active']} "
        f"dry_run={summary['dry_run']}"
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()
