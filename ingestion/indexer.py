"""Ingestion pipeline: embed chunks → write to Qdrant + BM25 + PostgreSQL."""

import hashlib
import logging
import os
import pickle
import threading
from pathlib import Path

from api.db import get_conn
from retrieval.bm25_store import _TURKISH_STOPWORDS

logger = logging.getLogger(__name__)

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
BM25_INDEX_DIR = Path(os.getenv("BM25_INDEX_DIR", "indexes"))
EMBED_BATCH_SIZE = 32
VECTOR_SIZE = 768

# Per-tenant locks guard concurrent BM25 read-modify-write operations.
_bm25_locks: dict[str, threading.Lock] = {}
_bm25_locks_mutex = threading.Lock()


def _bm25_lock(tenant_slug: str) -> threading.Lock:
    with _bm25_locks_mutex:
        if tenant_slug not in _bm25_locks:
            _bm25_locks[tenant_slug] = threading.Lock()
        return _bm25_locks[tenant_slug]


def _qdrant_client():
    from qdrant_client import QdrantClient
    return QdrantClient(url=QDRANT_URL)


def _ensure_collection(client, tenant_slug: str):
    from qdrant_client.models import Distance, VectorParams

    collection_name = f"tenant_{tenant_slug}"
    if not client.collection_exists(collection_name):
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

        from generation.llm import is_available
        from ingestion.embedder import embed

        # Contextual enrichment: prepend a 1-sentence LLM summary to each chunk.
        # Improves embedding recall by ~30-50% at the cost of extra inference per chunk.
        # Skipped gracefully if LLM not loaded (e.g. first boot before model download).
        if is_available():
            chunks = self._enrich_chunks(chunks, filename)
        else:
            logger.info("LLM unavailable — skipping contextual enrichment for doc %s", document_id)

        texts = [c["text"] for c in chunks]
        embeddings = embed(texts, batch_size=EMBED_BATCH_SIZE)
        logger.info("Embeddings computed: shape=%s", embeddings.shape)

        self._upsert_qdrant(document_id, tenant_slug, filename, chunks, embeddings)
        self._update_bm25(tenant_slug, chunks, document_id, filename)
        self._update_postgres_status(document_id, len(chunks))

        logger.info("Indexing complete for document %s", document_id)

    def _enrich_chunks(self, chunks: list[dict], filename: str) -> list[dict]:
        """Prepend a short LLM-generated context sentence to each chunk's text.

        Uses max_tokens=60 so each call takes ~3-5 s instead of ~40 s.
        Falls back to the original chunk on any error so ingestion never aborts.
        """
        from generation.citations import strip_think_tags
        from generation.llm import generate

        enriched = []
        total = len(chunks)
        logger.info("Contextual enrichment: %d chunks for '%s'", total, filename)

        for i, chunk in enumerate(chunks):
            try:
                snippet = chunk["text"][:300].replace("\n", " ")
                prompt = (
                    f"<|im_start|>system\n"
                    f"Verilen metin parçasının konusunu tek kısa Türkçe cümleyle belirt.<|im_end|>\n"
                    f"<|im_start|>user\n"
                    f"Belge: {filename}\nMetin: {snippet} /no_think<|im_end|>\n"
                    f"<|im_start|>assistant\n"
                )
                context_sentence = strip_think_tags(generate(prompt, max_tokens=60)).strip()
                if context_sentence:
                    enriched_text = f"[Bağlam: {context_sentence}]\n{chunk['text']}"
                    enriched.append({**chunk, "text": enriched_text})
                else:
                    enriched.append(chunk)
                logger.debug("Enriched chunk %d/%d", i + 1, total)
            except Exception as exc:
                logger.warning("Enrichment failed for chunk %d: %s — using original", i, exc)
                enriched.append(chunk)

        logger.info("Contextual enrichment complete for '%s'", filename)
        return enriched

    def _upsert_qdrant(self, document_id, tenant_slug, filename, chunks, embeddings):
        from qdrant_client.models import PointStruct

        client = _qdrant_client()
        collection_name = _ensure_collection(client, tenant_slug)

        points = []
        for chunk, vec in zip(chunks, embeddings, strict=False):
            key = f"{document_id}_{chunk['chunk_index']}".encode()
            point_id = int(hashlib.sha1(key).hexdigest(), 16) % (2**63)
            points.append(PointStruct(
                id=point_id,
                vector=vec.tolist(),
                payload={
                    "text": chunk["text"],
                    "doc_id": document_id,
                    "chunk_index": chunk["chunk_index"],
                    "filename": filename,
                    "start_char": chunk.get("start_char", 0),
                    "end_char": chunk.get("end_char", 0),
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
        payloads = [
            {
                "chunk_index": c["chunk_index"],
                "text": c["text"],
                "doc_id": document_id,
                "filename": filename,
                "start_char": c.get("start_char", 0),
                "end_char": c.get("end_char", 0),
            }
            for c in chunks
        ]

        with _bm25_lock(tenant_slug):
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
        conn = get_conn()
        try:
            with conn, conn.cursor() as cur:
                cur.execute(
                    "UPDATE documents SET status='ready', chunk_count=%s WHERE id=%s",
                    (chunk_count, document_id),
                )
            logger.info("PostgreSQL: document %s marked as ready (%d chunks)", document_id, chunk_count)
        except Exception as exc:
            logger.error("Failed to update PostgreSQL status: %s", exc)
        finally:
            conn.close()


def delete_document_vectors(document_id: str, tenant_slug: str):
    """Remove all Qdrant points and BM25 entries for a given document."""
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

    _remove_from_bm25(document_id, tenant_slug)


def _remove_from_bm25(document_id: str, tenant_slug: str):
    """Rebuild BM25 index for tenant_slug with document_id entries removed."""
    import bm25s

    index_path = BM25_INDEX_DIR / f"bm25_{tenant_slug}.pkl"
    if not index_path.exists():
        return

    with _bm25_lock(tenant_slug):
        if not index_path.exists():
            return

        with open(index_path, "rb") as f:
            data = pickle.load(f)

        kept = [
            (text, payload)
            for text, payload in zip(data["texts"], data["payloads"], strict=False)
            if payload.get("doc_id") != document_id
        ]

        if not kept:
            index_path.unlink()
            logger.info("BM25 index empty after removing doc=%s; file deleted", document_id)
            return

        texts, payloads = zip(*kept, strict=False)
        tokenized = bm25s.tokenize(list(texts), stopwords=_TURKISH_STOPWORDS)
        retriever = bm25s.BM25()
        retriever.index(tokenized)

        with open(index_path, "wb") as f:
            pickle.dump({"retriever": retriever, "texts": list(texts), "payloads": list(payloads)}, f)

    logger.info("BM25 index rebuilt for tenant '%s': %d docs remain after removing doc=%s",
                tenant_slug, len(texts), document_id)


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
