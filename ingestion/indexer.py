"""Ingestion pipeline: embed chunks → write to Qdrant + BM25 + PostgreSQL."""

import logging
import os
import pickle
from pathlib import Path

from api.db import get_conn

logger = logging.getLogger(__name__)

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
BM25_INDEX_DIR = Path(os.getenv("BM25_INDEX_DIR", "indexes"))
EMBED_BATCH_SIZE = 32
VECTOR_SIZE = 768


def _qdrant_client():
    from qdrant_client import QdrantClient
    return QdrantClient(url=QDRANT_URL)


def _ensure_collection(client, tenant_slug: str):
    from qdrant_client.models import Distance, VectorParams

    collection_name = f"tenant_{tenant_slug}"
    existing = [c.name for c in client.get_collections().collections]
    if collection_name not in existing:
        logger.info("Creating Qdrant collection: %s", collection_name)
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
    return collection_name


class TenantIndexer:
    """Write parsed chunks into Qdrant (dense), BM25 (sparse), and PostgreSQL."""

    def ingest(
        self,
        document_id: str,
        tenant_slug: str,
        filename: str,
        chunks: list[dict],
    ) -> None:
        """Index all chunks for a document under the given tenant.

        Steps:
        1. Embed all chunks in batches of EMBED_BATCH_SIZE.
        2. Upsert to Qdrant with payload {text, doc_id, chunk_index, filename}.
        3. Add to BM25 index (load existing or create new).
        4. Persist BM25 index to disk.
        5. Update document status in PostgreSQL to 'ready'.
        """
        if not chunks:
            logger.warning("No chunks to index for document %s", document_id)
            return

        logger.info("Indexing %d chunks for doc=%s tenant=%s", len(chunks), document_id, tenant_slug)

        from ingestion.embedder import embed

        texts = [c["text"] for c in chunks]
        embeddings = embed(texts, batch_size=EMBED_BATCH_SIZE)
        logger.info("Embeddings computed: shape=%s", embeddings.shape)

        self._upsert_qdrant(document_id, tenant_slug, filename, chunks, embeddings)
        self._update_bm25(tenant_slug, chunks, document_id, filename)
        self._update_postgres_status(document_id, len(chunks))

        logger.info("Indexing complete for document %s", document_id)

    def _upsert_qdrant(self, document_id, tenant_slug, filename, chunks, embeddings):
        from qdrant_client.models import PointStruct

        client = _qdrant_client()
        collection_name = _ensure_collection(client, tenant_slug)

        points = []
        for chunk, vec in zip(chunks, embeddings, strict=False):
            point_id = abs(hash(f"{document_id}_{chunk['chunk_index']}")) % (2**63)
            points.append(PointStruct(
                id=point_id,
                vector=vec.tolist(),
                payload={
                    "text": chunk["text"],
                    "doc_id": document_id,
                    "chunk_index": chunk["chunk_index"],
                    "filename": filename,
                    "start_char": chunk["start_char"],
                    "end_char": chunk["end_char"],
                },
            ))

        BATCH = 100
        for i in range(0, len(points), BATCH):
            client.upsert(collection_name=collection_name, points=points[i:i + BATCH])
            logger.debug("Upserted Qdrant batch %d-%d", i, min(i + BATCH, len(points)))

        logger.info("Upserted %d points to Qdrant collection '%s'", len(points), collection_name)

    def _update_bm25(self, tenant_slug: str, chunks: list[dict], document_id: str = "", filename: str = ""):
        import bm25s

        BM25_INDEX_DIR.mkdir(parents=True, exist_ok=True)
        index_path = BM25_INDEX_DIR / f"bm25_{tenant_slug}.pkl"

        texts = [c["text"] for c in chunks]
        payloads = [{"chunk_index": c["chunk_index"], "text": c["text"], "doc_id": document_id, "filename": filename} for c in chunks]

        # Load existing index corpus if present
        if index_path.exists():
            with open(index_path, "rb") as f:
                existing = pickle.load(f)
            all_texts = existing["texts"] + texts
            all_payloads = existing["payloads"] + payloads
        else:
            all_texts = texts
            all_payloads = payloads

        tokenized = bm25s.tokenize(all_texts, stopwords=_TURKISH_STOPWORDS)
        retriever = bm25s.BM25()
        retriever.index(tokenized)

        with open(index_path, "wb") as f:
            pickle.dump({
                "retriever": retriever,
                "texts": all_texts,
                "payloads": all_payloads,
            }, f)

        logger.info("BM25 index updated: %d total docs at %s", len(all_texts), index_path)

    def _update_postgres_status(self, document_id: str, chunk_count: int):
        try:
            conn = get_conn()
            with conn, conn.cursor() as cur:
                cur.execute(
                    "UPDATE documents SET status='ready', chunk_count=%s WHERE id=%s",
                    (chunk_count, document_id),
                )
            conn.close()
            logger.info("PostgreSQL: document %s marked as ready (%d chunks)", document_id, chunk_count)
        except Exception as exc:
            logger.error("Failed to update PostgreSQL status: %s", exc)


def delete_document_vectors(document_id: str, tenant_slug: str):
    """Remove all Qdrant points for a given document."""
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    client = _qdrant_client()
    collection_name = f"tenant_{tenant_slug}"
    client.delete(
        collection_name=collection_name,
        points_selector=Filter(
            must=[FieldCondition(key="doc_id", match=MatchValue(value=document_id))]
        ),
    )
    logger.info("Deleted Qdrant points for doc=%s in collection=%s", document_id, collection_name)


_TURKISH_STOPWORDS = [
    "bir", "bu", "şu", "o", "da", "de", "ki", "ile", "için",
    "ve", "veya", "ama", "fakat", "çünkü", "gibi", "kadar",
    "daha", "en", "çok", "az", "her", "hiç", "ne", "nasıl",
    "olan", "olarak", "ise", "hem", "ya", "mi", "mı", "mu",
    "mü", "değil", "var", "yok", "ben", "sen", "biz", "siz", "onlar",
]


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    from ingestion.chunker import TurkishChunker
    from ingestion.parser import parse_document

    if len(sys.argv) < 4:
        print("Usage: python -m ingestion.indexer <file> <tenant_slug> <doc_id>")
        sys.exit(1)

    file_path, tenant_slug, doc_id = sys.argv[1], sys.argv[2], sys.argv[3]
    text = parse_document(file_path)
    chunks = TurkishChunker().chunk(text)
    print(f"Parsed {len(chunks)} chunks")
    TenantIndexer().ingest(doc_id, tenant_slug, Path(file_path).name, chunks)
    print("Done.")
