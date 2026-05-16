"""Hybrid retrieval: BM25 + dense Qdrant fused via Reciprocal Rank Fusion (RRF).

Pipeline:
  1. Embed query with the singleton embedder.
  2. BM25 search → top_k sparse hits.
  3. Qdrant dense search → top_k dense hits.
  4. RRF fusion: score = Σ 1/(rank + RRF_K) across both ranked lists.
  5. Re-rank the top-10 fused candidates with a cross-encoder.
  6. Return final_k results with text, source, score, chunk_index.
"""

import logging
from concurrent.futures import ThreadPoolExecutor

from retrieval.bm25_store import BM25Store
from retrieval.reranker import rerank
from retrieval.vector_store import VectorStore

import os

logger = logging.getLogger(__name__)

RRF_K = 60  # standard RRF constant
RERANK_CANDIDATES = 10
# Cross-encoder logit threshold below which results are considered off-topic.
# ms-marco-MiniLM-L-6-v2 raw logits: relevant ≈ 0–10, irrelevant ≈ negative.
# -2.0 is conservative — only rejects clearly off-topic queries.
CONFIDENCE_THRESHOLD = float(os.getenv("RERANK_CONFIDENCE_THRESHOLD", "-2.0"))


class HybridRetriever:
    """Run hybrid BM25 + dense retrieval with RRF fusion and cross-encoder reranking."""

    def retrieve(
        self,
        query: str,
        tenant_slug: str,
        top_k: int = 20,
        final_k: int = 5,
    ) -> list[dict]:
        """Return final_k most relevant chunks for query within the tenant's index.

        Each result dict contains: text, doc_id, chunk_index, filename, score.
        """

        from ingestion.embedder import embed

        logger.info("Hybrid retrieval: query='%s...' tenant=%s top_k=%d final_k=%d",
                    query[:50], tenant_slug, top_k, final_k)

        # Step 1: embed query
        query_vec = embed([query])[0].tolist()

        # Step 2 & 3: sparse + dense search — run both in parallel via threads
        with ThreadPoolExecutor(max_workers=2) as pool:
            bm25_future = pool.submit(BM25Store(tenant_slug).search, query, top_k)
            dense_future = pool.submit(VectorStore(tenant_slug).search, query_vec, top_k)
            bm25_hits = bm25_future.result()
            dense_hits = dense_future.result()

        if not bm25_hits and not dense_hits:
            logger.warning("No results from either BM25 or dense search for tenant '%s'", tenant_slug)
            return []

        # Step 4: RRF fusion
        fused = self._rrf_fusion(bm25_hits, dense_hits)

        # Take top RERANK_CANDIDATES for re-ranking
        candidates = fused[:RERANK_CANDIDATES]

        # Step 5: cross-encoder reranking (falls back to RRF order if model unavailable)
        if len(candidates) > 1:
            passages = [c["text"] for c in candidates]
            try:
                rerank_scores = rerank(query, passages)
                for c, score in zip(candidates, rerank_scores, strict=False):
                    c["rerank_score"] = score
                candidates.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
            except Exception as exc:
                logger.warning("Reranker unavailable (%s) — using RRF order", exc)
                for c in candidates:
                    c["rerank_score"] = c["rrf_score"]
        else:
            for c in candidates:
                c["rerank_score"] = c["rrf_score"]

        # Step 6: confidence gate — drop results when best score is off-topic
        top_score = candidates[0].get("rerank_score", 0) if candidates else 0
        if top_score < CONFIDENCE_THRESHOLD:
            logger.info(
                "Low confidence (%.2f < %.2f) for query='%s...' tenant=%s — returning empty",
                top_score, CONFIDENCE_THRESHOLD, query[:40], tenant_slug,
            )
            return []

        results = candidates[:final_k]
        logger.info("Retrieved %d chunks after reranking (top_score=%.2f)", len(results), top_score)
        return results

    def _rrf_fusion(self, bm25_hits: list[dict], dense_hits: list[dict]) -> list[dict]:
        """Merge two ranked lists via Reciprocal Rank Fusion."""
        scores: dict[str, float] = {}
        # Key candidates by (doc_id, chunk_index) to deduplicate
        lookup: dict[str, dict] = {}

        def _key(hit: dict) -> str:
            return f"{hit.get('doc_id', '')}_{hit.get('chunk_index', hit.get('text', '')[:30])}"

        for rank, hit in enumerate(bm25_hits):
            k = _key(hit)
            scores[k] = scores.get(k, 0.0) + 1.0 / (rank + RRF_K)
            if k not in lookup:
                lookup[k] = hit

        for rank, hit in enumerate(dense_hits):
            k = _key(hit)
            scores[k] = scores.get(k, 0.0) + 1.0 / (rank + RRF_K)
            if k not in lookup:
                lookup[k] = hit

        fused = []
        for k, rrf_score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
            entry = {**lookup[k], "rrf_score": rrf_score}
            fused.append(entry)

        logger.debug("RRF fusion: %d BM25 + %d dense → %d unique candidates",
                     len(bm25_hits), len(dense_hits), len(fused))
        return fused


if __name__ == "__main__":
    import json
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if len(sys.argv) < 3:
        print("Usage: python -m retrieval.hybrid <tenant_slug> <query>")
        sys.exit(1)

    tenant_slug = sys.argv[1]
    query = " ".join(sys.argv[2:])
    results = HybridRetriever().retrieve(query, tenant_slug)
    print(json.dumps(results, ensure_ascii=False, indent=2))
