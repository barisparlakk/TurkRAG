"""Ingest sample Turkish documents under a demo tenant.

Creates the demo tenant if it does not exist, then indexes
all .txt/.pdf/.docx files found in data/sample/.

Usage:
  python scripts/ingest_demo.py [--tenant demo]
"""

import argparse
import logging
import os
import sys
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://turkrag:turkrag_secret@localhost/turkrag")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
SAMPLE_DIR = Path("data/sample")


def _ensure_tenant(name: str, slug: str) -> str:
    """Return tenant_id, creating the tenant if needed."""
    import psycopg2

    conn = psycopg2.connect(POSTGRES_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM tenants WHERE slug=%s", (slug,))
            row = cur.fetchone()
            if row:
                logger.info("Tenant '%s' already exists: %s", slug, row[0])
                return str(row[0])

            tenant_id = str(uuid.uuid4())
            with conn:
                with conn.cursor() as c:
                    c.execute(
                        "INSERT INTO tenants (id, name, slug) VALUES (%s, %s, %s)",
                        (tenant_id, name, slug),
                    )
            logger.info("Created tenant '%s' (%s)", slug, tenant_id)
            return tenant_id
    finally:
        conn.close()


def _ensure_qdrant_collection(slug: str):
    from qdrant_client import QdrantClient
    from qdrant_client.models import VectorParams, Distance

    client = QdrantClient(url=QDRANT_URL)
    collection_name = f"tenant_{slug}"
    existing = [c.name for c in client.get_collections().collections]
    if collection_name not in existing:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=768, distance=Distance.COSINE),
        )
        logger.info("Created Qdrant collection: %s", collection_name)


def ingest_file(file_path: Path, tenant_id: str, tenant_slug: str):
    """Parse, chunk and index a single file."""
    import psycopg2
    import hashlib
    from ingestion.parser import parse_document
    from ingestion.chunker import TurkishChunker
    from ingestion.indexer import TenantIndexer

    content = file_path.read_bytes()
    file_hash = hashlib.sha256(content).hexdigest()

    conn = psycopg2.connect(POSTGRES_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM documents WHERE tenant_id=%s AND file_hash=%s", (tenant_id, file_hash))
            if cur.fetchone():
                logger.info("Skipping already-indexed file: %s", file_path.name)
                return

        doc_id = str(uuid.uuid4())
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO documents (id, tenant_id, filename, file_hash, status) VALUES (%s,%s,%s,%s,'processing')",
                    (doc_id, tenant_id, file_path.name, file_hash),
                )
    finally:
        conn.close()

    logger.info("Ingesting: %s", file_path.name)
    text = parse_document(str(file_path))
    chunks = TurkishChunker().chunk(text)
    logger.info("  %d chars → %d chunks", len(text), len(chunks))

    TenantIndexer().ingest(doc_id, tenant_slug, file_path.name, chunks)
    logger.info("  Done: %s", file_path.name)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")

    parser = argparse.ArgumentParser(description="Ingest demo Turkish documents")
    parser.add_argument("--tenant", default="demo", help="Tenant slug (default: demo)")
    args = parser.parse_args()

    tenant_name = args.tenant.capitalize() + " Demo"
    tenant_slug = args.tenant

    print(f"\nTurkRAG Demo Ingestion\n{'='*40}")
    print(f"Tenant: {tenant_slug}")
    print(f"Sample dir: {SAMPLE_DIR.resolve()}\n")

    tenant_id = _ensure_tenant(tenant_name, tenant_slug)
    _ensure_qdrant_collection(tenant_slug)

    files = sorted(SAMPLE_DIR.glob("*"))
    supported = {".pdf", ".docx", ".txt"}
    files = [f for f in files if f.suffix.lower() in supported]

    if not files:
        print(f"No supported files found in {SAMPLE_DIR}.")
        print("Create .txt/.pdf/.docx files in data/sample/ and re-run.")
        sys.exit(0)

    for f in files:
        ingest_file(f, tenant_id, tenant_slug)

    print(f"\n✓ Ingested {len(files)} files for tenant '{tenant_slug}'")
    print(f"\nTo query the demo tenant, get a token:")
    print(f"  curl -X POST http://localhost:8000/auth/token \\")
    print(f'    -H "Content-Type: application/json" \\')
    print(f'    -d \'{{"tenant_id":"{tenant_id}","user_id":"demo","role":"member"}}\'')
