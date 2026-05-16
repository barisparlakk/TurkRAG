# TurkRAG Architecture

Plain-text explanation of the RAG pipeline, component responsibilities, and data flow.

---

## Overview

TurkRAG is a retrieval-augmented generation (RAG) system designed for Turkish enterprise use. Tenants upload their own documents; an on-premise LLM answers questions using only those documents. No data leaves the server.

---

## Ingestion Pipeline

When a document is uploaded via `POST /documents/upload`, a background task runs:

```
File (PDF / DOCX / TXT / XLSX / CSV)
  ↓ ingestion/parser.py
  Plain text

  ↓ ingestion/chunker.py  (TurkishChunker)
  Chunks: [{text, chunk_index, start_char, end_char}, ...]

  ↓ ingestion/embedder.py  (local SentenceTransformer)
  Dense vectors: np.ndarray shape (N, 768), L2-normalised

  ↓ ingestion/indexer.py  (TenantIndexer)
  → Qdrant collection  (dense vectors + payload)
  → BM25s index on disk  (sparse keyword index)
  → PostgreSQL documents table  (metadata, status)
```

### Turkish Chunker

`TurkishChunker` splits text on sentence boundaries detected by a regex that understands Turkish abbreviations (`Dr.`, `Prof.`, `vs.`, `vb.`, `No.`, etc.) and digit-period sequences (e.g. `1.5 kg`). It uses the `regex` package for variable-width lookbehinds, which `re` does not support.

- Max chunk size: 800 characters (~400 tokens)
- Overlap: 150 characters (last sentence(s) of previous chunk prepended)
- Short sentences (< 40 chars) are merged with the next sentence before chunking

### Embedder

Loads a SentenceTransformer from a **local directory** (`models/turkish-embedder/` by default). If the path does not exist the API raises a `RuntimeError` at startup — there is no HuggingFace Hub fallback. Embeddings are L2-normalised, so inner product equals cosine similarity.

---

## Retrieval Pipeline

On each chat query:

```
User query
  ↓ ingestion/embedder.py  (same model, same normalisation)
  Query vector

  ├─ retrieval/bm25_store.py   BM25 search → top-K sparse hits
  └─ retrieval/vector_store.py  Qdrant search → top-K dense hits
        (both run in parallel via ThreadPoolExecutor)

  ↓ retrieval/hybrid.py  (_rrf_fusion)
  Reciprocal Rank Fusion: score(d) = Σ 1/(rank_i + 60)
  → merged ranked list (up to 20 candidates)

  ↓ retrieval/reranker.py  (cross-encoder ms-marco-MiniLM-L-6-v2)
  Re-scores top-10 candidates with query+passage pairs

  → final_k=5 chunks  [{text, doc_id, filename, chunk_index, score}]
```

### Why RRF?

BM25 captures exact keyword matches; dense retrieval captures semantic similarity. Neither dominates for all queries. RRF merges them without needing calibrated scores — only ranks matter. k=60 is the standard value that dampens rank sensitivity.

### Why a Cross-Encoder Reranker?

Bi-encoder embeddings (used in retrieval) encode query and passage independently — fast but imprecise. A cross-encoder sees the query+passage pair jointly and scores relevance more accurately. Running it on only 10 candidates keeps latency acceptable.

---

## Generation Pipeline

```
Query + retrieved chunks + conversation history
  ↓ generation/prompt.py  (build_prompt)
  ChatML-formatted prompt:
    <|im_start|>system  — Turkish system prompt (answer only from docs)
    [history turns]     — last 4 user/assistant pairs
    <|im_start|>user    — context chunks + question + /no_think
    <|im_start|>assistant

  ↓ generation/llm.py  (Qwen3-8B-Instruct GGUF via llama-cpp-python)
  Token stream

  ↓ generation/streamer.py  (stream_rag_response)
  WebSocket frames: {"type":"token","content":"..."} per token
                    {"type":"done","citations":[...],"session_id":"..."}

  ↓ generation/citations.py
  Extract [Kaynak N] references → CitationSource objects
  Strip residual <think>...</think> blocks
```

### System Prompt

The Turkish system prompt instructs the model to:
1. Answer only from the provided context chunks
2. Never fabricate information not in the documents
3. Cite sources at the end of the answer (`[Kaynak 1]` style)
4. Admit when a question cannot be answered from the documents

`/no_think` is appended to the user turn to suppress Qwen3's internal chain-of-thought scratchpad, reducing latency and token usage.

---

## API Layer

`api/main.py` creates the FastAPI app and initialises the PostgreSQL schema on startup.

### Multi-tenancy

Each tenant has an isolated:
- Qdrant collection (named by tenant slug)
- BM25 index directory
- PostgreSQL rows (documents, sessions, messages, query_logs)

All endpoints depend-inject `tenant_id` from the JWT. No cross-tenant data leakage is possible at the query level.

### Session Management

`/chat` and `/chat/stream` both support conversation continuity:
- Client omits `session_id` → new session created, UUID returned
- Client passes `session_id` → history loaded (last 8 messages = 4 turns)
- Messages (user + assistant) persisted to PostgreSQL after each turn

### Streaming

`/chat/stream` is a WebSocket endpoint. The client sends one JSON message; the server streams `{"type":"token"}` frames during generation, then a final `{"type":"done"}` frame containing citations and `session_id`.

---

## Data Storage

| Store | What | Where |
|-------|------|-------|
| PostgreSQL | Tenants, documents metadata, sessions, messages, query_logs | `POSTGRES_URL` |
| Qdrant | Dense chunk vectors + payload | `QDRANT_URL` |
| Disk | BM25 indexes | `BM25_INDEX_DIR` (default: `indexes/`) |
| Disk | Uploaded files (temporary) | `UPLOAD_DIR` (default: `/tmp/uploads`) |
| Disk | LLM model | `LLM_MODEL_PATH` |
| Disk | Embedding model | `TURKISH_EMBEDDER_PATH` |

PostgreSQL indexes exist on `sessions(tenant_id)`, `messages(session_id)`, `query_logs(tenant_id)`, and `documents(tenant_id)`.

---

## Analytics

`GET /analytics/stats` returns per-tenant:
- Total query count, queries in last 24h, average latency
- Top 5 most-asked questions (exact match)
- Top 5 most-cited documents (from JSONB citation arrays in messages)

`GET /analytics/recent` returns the last N query log entries.

The React dashboard exposes these in the **Analitik** tab.

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Local-only embedder (no HF Hub fallback) | KVKK / air-gap compliance; prevents silent network calls in production |
| GGUF + llama-cpp-python | Runs on CPU/GPU without full PyTorch stack; quantized for RAM efficiency |
| RRF over learned fusion | No training data needed; works out-of-the-box across document types |
| Character-based chunking (not token-based) | Avoids tokenizer dependency in ingestion; ~2 chars/token for Turkish |
| psycopg2 (sync) | Simple; async pg drivers add complexity without benefit at current scale |
| WebSocket for streaming | Native browser API; avoids SSE buffering issues in some reverse proxies |
