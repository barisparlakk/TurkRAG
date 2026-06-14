"""CLI to provision a new tenant in TurkRAG.

Usage:
  python scripts/create_tenant.py --name "Acme Şirketi" --slug "acme"
"""

import argparse
import logging
import os
import sys
import uuid

logger = logging.getLogger(__name__)

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://turkrag:turkrag_secret@localhost/turkrag")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")


def create_tenant(name: str, slug: str, admin_email: str | None = None, admin_password: str | None = None) -> dict:
    """Create tenant in PostgreSQL and provision Qdrant collection."""
    import psycopg2

    conn = psycopg2.connect(POSTGRES_URL)
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SELECT id FROM tenants WHERE slug=%s", (slug,))
            if cur.fetchone():
                print(f"✗ Tenant slug '{slug}' already exists.")
                sys.exit(1)

            tenant_id = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO tenants (id, name, slug) VALUES (%s, %s, %s) RETURNING id, name, slug, created_at",
                (tenant_id, name, slug),
            )
            row = cur.fetchone()
            if admin_email and admin_password:
                from api.auth import hash_password
                cur.execute(
                    """INSERT INTO users (tenant_id, email, password_hash, role, is_active)
                       VALUES (%s, %s, %s, 'admin', true)
                       ON CONFLICT DO NOTHING""",
                    (tenant_id, admin_email.strip().lower(), hash_password(admin_password)),
                )
    finally:
        conn.close()

    print(f"✓ Tenant created in PostgreSQL: id={row[0]}  name={row[1]}  slug={row[2]}")

    # Provision Qdrant
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams

        client = QdrantClient(url=QDRANT_URL)
        collection_name = f"tenant_{slug}"
        if not client.collection_exists(collection_name):
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=768, distance=Distance.COSINE),
            )
            print(f"✓ Qdrant collection created: {collection_name}")
        else:
            print(f"  Qdrant collection already exists: {collection_name}")
    except Exception as exc:
        print(f"  Warning: Could not create Qdrant collection: {exc}")

    if admin_email and admin_password:
        print(f"✓ Initial admin user created: {admin_email.strip().lower()}")
    else:
        print("  No admin user created. Pass --admin-email and --admin-password to bootstrap login.")

    return {"id": str(row[0]), "name": row[1], "slug": row[2]}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Create a new TurkRAG tenant")
    parser.add_argument("--name", required=True, help="Tenant display name")
    parser.add_argument("--slug", required=True, help="Tenant slug (lowercase alphanumeric + hyphens)")
    parser.add_argument("--admin-email", default="", help="Initial admin email")
    parser.add_argument("--admin-password", default="", help="Initial admin password")
    args = parser.parse_args()

    result = create_tenant(args.name, args.slug, args.admin_email or None, args.admin_password or None)
    print(f"\nDone. Tenant '{result['name']}' is ready.")
