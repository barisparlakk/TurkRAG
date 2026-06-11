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
import os
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from retrieval.bm25_store import BM25Store
from retrieval.vector_store import VectorStore

logger = logging.getLogger(__name__)

RRF_K = 60  # standard RRF constant
RERANK_CANDIDATES = 10
# Cross-encoder logit threshold below which results are considered off-topic.
# ms-marco-MiniLM-L-6-v2 raw logits: relevant ≈ 0–10, irrelevant ≈ negative.
# -2.0 is conservative — only rejects clearly off-topic queries.
CONFIDENCE_THRESHOLD = float(os.getenv("RERANK_CONFIDENCE_THRESHOLD", "-2.0"))

# HyDE: embed a hypothetical answer instead of the raw query for dense retrieval.
# Improves recall for question-style queries. Disabled automatically if LLM unavailable.
HYDE_ENABLED = os.getenv("HYDE_ENABLED", "true").lower() == "true"
HYDE_MAX_TOKENS = int(os.getenv("HYDE_MAX_TOKENS", "80"))


def _hyde_embed(query: str) -> list[float] | None:
    """Generate a short hypothetical answer and return its embedding.

    Returns None if LLM is unavailable or generation fails — caller falls back
    to the raw query embedding.
    """
    try:
        from generation.citations import strip_think_tags
        from generation.llm import generate, is_available
        from ingestion.embedder import embed

        if not is_available():
            return None

        prompt = (
            "<|im_start|>system\n"
            "Soruya kısa bir Türkçe paragrafla yanıt ver. "
            "Bilmiyorsan tahmini bir yanıt yaz.<|im_end|>\n"
            f"<|im_start|>user\n{query} /no_think<|im_end|>\n"
            "<|im_start|>assistant\n"
        )
        hypo = strip_think_tags(generate(prompt, max_tokens=HYDE_MAX_TOKENS)).strip()
        if not hypo:
            return None
        vec = embed([hypo])[0]
        logger.debug("HyDE: generated hypothetical answer (%d chars)", len(hypo))
        return vec.tolist()
    except Exception as exc:
        logger.warning("HyDE generation failed: %s — using raw query embedding", exc)
        return None


RETRIEVAL_MODES = ("sparse", "dense", "hybrid", "hybrid+rerank")


class HybridRetriever:
    """Run hybrid BM25 + dense retrieval with RRF fusion and cross-encoder reranking.

    Retrieval modes
    ---------------
    sparse        — BM25 only (keyword matching baseline)
    dense         — Qdrant dense vectors only (semantic baseline)
    hybrid        — RRF fusion of BM25 + dense, no reranker
    hybrid+rerank — RRF fusion + cross-encoder reranker + MMR (default, full pipeline)
    """

    def retrieve(
        self,
        query: str,
        tenant_slug: str,
        top_k: int = 20,
        final_k: int = 5,
        mode: str = "hybrid+rerank",
    ) -> list[dict]:
        """Return final_k most relevant chunks for *query* within the tenant's index.

        Each result dict contains: text, doc_id, chunk_index, filename, score,
        retrieval_mode.
        """
        if mode not in RETRIEVAL_MODES:
            raise ValueError(f"mode must be one of {RETRIEVAL_MODES}, got '{mode}'")

        from ingestion.embedder import embed

        logger.info(
            "Retrieval [mode=%s]: query='%s...' tenant=%s top_k=%d final_k=%d",
            mode, query[:50], tenant_slug, top_k, final_k,
        )

        # ── Step 1: embed query (needed for dense / hybrid modes) ──────────────
        if mode in ("dense", "hybrid", "hybrid+rerank"):
            query_vec_raw = embed([query])[0]

            if HYDE_ENABLED and mode in ("hybrid", "hybrid+rerank"):
                hyde_vec = _hyde_embed(query)
                if hyde_vec is not None:
                    blended = (query_vec_raw + np.array(hyde_vec)) / 2.0
                    norm = np.linalg.norm(blended)
                    query_vec = (blended / norm if norm > 0 else blended).tolist()
                    logger.debug("HyDE: using blended query+hypothesis embedding")
                else:
                    query_vec = query_vec_raw.tolist()
            else:
                query_vec = query_vec_raw.tolist()
        else:
            query_vec = None

        # ── Step 2: retrieve from the selected source(s) ──────────────────────
        if mode == "sparse":
            hits = BM25Store(tenant_slug).search(query, top_k)
            if not hits:
                logger.warning("BM25 returned no results for tenant '%s'", tenant_slug)
                return []
            for h in hits:
                h["rrf_score"] = h.get("score", 0.0)
            candidates = hits[:final_k]
            for c in candidates:
                c["rerank_score"] = c["rrf_score"]
                c["_reranker_used"] = False
            return self._tag(candidates[:final_k], mode)

        if mode == "dense":
            hits = VectorStore(tenant_slug).search(query_vec, top_k)
            if not hits:
                logger.warning("Dense search returned no results for tenant '%s'", tenant_slug)
                return []
            for h in hits:
                h["rrf_score"] = h.get("score", 0.0)
            candidates = hits[:final_k]
            for c in candidates:
                c["rerank_score"] = c["rrf_score"]
                c["_reranker_used"] = False
            return self._tag(candidates[:final_k], mode)

        # hybrid / hybrid+rerank: parallel BM25 + dense
        with ThreadPoolExecutor(max_workers=2) as pool:
            bm25_future = pool.submit(BM25Store(tenant_slug).search, query, top_k)
            dense_future = pool.submit(VectorStore(tenant_slug).search, query_vec, top_k)
            bm25_hits = bm25_future.result()
            dense_hits = dense_future.result()

        if not bm25_hits and not dense_hits:
            logger.warning("No results from either BM25 or dense search for tenant '%s'", tenant_slug)
            return []

        fused = self._rrf_fusion(bm25_hits, dense_hits)
        candidates = fused[:RERANK_CANDIDATES]

        # ── Step 3: optional cross-encoder reranking ──────────────────────────
        if mode == "hybrid+rerank" and len(candidates) > 1:
            from retrieval.reranker import rerank

            passages = [c["text"] for c in candidates]
            try:
                rerank_scores = rerank(query, passages)
                for c, score in zip(candidates, rerank_scores, strict=False):
                    c["rerank_score"] = score
                    c["_reranker_used"] = True
                candidates.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
            except Exception as exc:
                logger.warning("Reranker unavailable (%s) — falling back to RRF order", exc)
                for c in candidates:
                    c["rerank_score"] = c["rrf_score"]
                    c["_reranker_used"] = False
        else:
            for c in candidates:
                c["rerank_score"] = c["rrf_score"]
                c["_reranker_used"] = False

        # ── Step 4: confidence gate (only for full pipeline) ──────────────────
        if mode == "hybrid+rerank":
            top_score = candidates[0].get("rerank_score", 0) if candidates else 0
            if top_score < CONFIDENCE_THRESHOLD:
                logger.info(
                    "Low confidence (%.2f < %.2f) for query='%s...' tenant=%s — returning empty",
                    top_score, CONFIDENCE_THRESHOLD, query[:40], tenant_slug,
                )
                return []
            results = _mmr(candidates, final_k, lambda_param=0.5)
        else:
            results = candidates[:final_k]

        logger.info("Retrieved %d chunks [mode=%s]", len(results), mode)
        return self._tag(results, mode)

    @staticmethod
    def _tag(results: list[dict], mode: str) -> list[dict]:
        """Attach retrieval_mode to every result dict."""
        for r in results:
            r["retrieval_mode"] = mode
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


def _mmr(candidates: list[dict], k: int, lambda_param: float = 0.5) -> list[dict]:
    """Maximal Marginal Relevance: balance relevance vs. diversity.

    lambda_param=1.0 → pure relevance (same as top-k).
    lambda_param=0.0 → pure diversity.
    0.5 is a good default for RAG where duplicate chunks hurt more than help.

    Uses TF-IDF-style token overlap as a cheap similarity proxy — no extra
    embedding calls needed.
    """
    if len(candidates) <= k:
        return candidates

    def _token_set(text: str) -> set:
        return set(text.lower().split())

    selected: list[dict] = []
    remaining = list(candidates)

    while len(selected) < k and remaining:
        if not selected:
            # First pick: highest relevance score
            best = max(remaining, key=lambda c: c.get("rerank_score", 0))
        else:
            # MMR score = λ * relevance − (1−λ) * max_similarity_to_selected
            selected_tokens = [_token_set(s["text"]) for s in selected]

            def _mmr_score(c, current_selected_tokens=selected_tokens):
                rel = c.get("rerank_score", 0)
                c_tokens = _token_set(c["text"])
                max_sim = max(
                    len(c_tokens & s) / max(len(c_tokens | s), 1)
                    for s in current_selected_tokens
                )
                return lambda_param * rel - (1 - lambda_param) * max_sim

            best = max(remaining, key=_mmr_score)

        selected.append(best)
        remaining.remove(best)

    return selected


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
