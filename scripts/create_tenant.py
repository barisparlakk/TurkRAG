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


def create_tenant(name: str, slug: str) -> dict:
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

    # Print a dev JWT for this tenant
    from api.auth import create_token
    token = create_token(tenant_id=str(row[0]), user_id="admin", role="admin")
    print(f"\n✓ Admin JWT (expires 24h):\n  {token}\n")
    print("Use this token as: Authorization: Bearer <token>")

    return {"id": str(row[0]), "name": row[1], "slug": row[2]}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Create a new TurkRAG tenant")
    parser.add_argument("--name", required=True, help="Tenant display name")
    parser.add_argument("--slug", required=True, help="Tenant slug (lowercase alphanumeric + hyphens)")
    args = parser.parse_args()

    result = create_tenant(args.name, args.slug)
    print(f"\nDone. Tenant '{result['name']}' is ready.")
