## Shift Start — 2026-05-16
- Status: Large batch of uncommitted changes across API, generation, ingestion, dashboard. Core files (chunker, embedder, hybrid, llm, chat router) exist and are largely complete. No tests yet.
- First task: Commit existing changes in logical groups, then fix spec violations (chunker return keys, embedder HuggingFace fallback), then write tests.
- Known risks: chunker returns wrong key names (index/char_start instead of chunk_index/start_char/end_char); embedder falls back to HuggingFace Hub in violation of spec.

## Log
- feat(api): session management, message history, query analytics (b2bd216)
- feat(ingestion): Excel/CSV parsing (b42a962)
- refactor(api): extract api/db.py, fix multi-row INSERT, JOIN, indexes, parser helper, App.jsx ternaries (832e2ed)
- feat(generation): history in prompt, session_id in streamer, parallel retrieval (aac0431)
- feat(dashboard): analytics tab, session continuity, new chat button (66c41dd)
## Shift End (Session 1)
- Completed: session mgmt + analytics backend, Excel/CSV ingestion, api/db.py extraction, generation history/session_id, parallel retrieval, dashboard analytics tab + new chat, chunker spec keys, offline-only embedder, 35 tests (chunker/hybrid/API), test cleanup (parametrize), docs/architecture.md, README updates
- Remaining: nothing from priority list
- Decisions made: embedder raises on missing path (no HF fallback); character-based chunking kept (avoids tokenizer dep); psycopg2 kept over asyncpg (simplicity); connection pooling deferred (would need psycopg2.pool or asyncpg migration, out of scope)
- Review before push: api/db.py is new shared module — verify all callers import get_conn correctly; sessions table uses gen_random_uuid() via RETURNING — requires pg13+

## Shift Continuation — 2026-05-16 (Session 4)

### Bugs fixed
- `retrieval/hybrid.py`: reranker unavailable raised through entire chat endpoint. Fix: wrap `rerank()` in try/except, fall back to RRF order.
- `api/routers/chat.py` (`_log_query`, `_save_messages`): `conn = get_conn()` before `try:` — if DB down, exception killed the response after answer was computed. Fix: `conn = None` before try, set inside, `if conn is not None: conn.close()` in finally. Both now best-effort (catch all exceptions).
- `api/routers/documents.py` (`_ingest_document`): same pattern — background task stuck in "processing" on DB failure. Fixed.
- `ingestion/indexer.py`: `hash()` is non-deterministic across process restarts (PYTHONHASHSEED). `point_id` changed on restart → `upsert` created duplicate Qdrant points. Fixed: use `hashlib.sha1` for deterministic IDs.
- `ingestion/indexer.py`: race condition on BM25 read-modify-write — two concurrent uploads for same tenant could corrupt the index. Fix: per-tenant `threading.Lock` dictionary guards all BM25 operations.
- `api/main.py` (`query_logs` schema): `tenant_id` had no FK → orphaned rows on tenant delete. Fixed: `REFERENCES tenants(id) ON DELETE CASCADE`; `session_id` now `REFERENCES sessions(id) ON DELETE SET NULL`.
- `dashboard/src/components/CitationPanel.jsx`: `…` always appended even to short (non-truncated) previews. Fixed: only show `…` when `text_preview.length >= 120`.
- `generation/streamer.py`: on client disconnect, LLM producer thread kept running (wasting GPU). Fix: `threading.Event` cancellation signal; consumer sets it on exception, producer breaks on next token.

### New tests (session 4)
- `test_hybrid.py::TestRerankerFallback` (3) — fallback to RRF order when reranker raises.
- `test_indexer.py::TestDeterministicPointId` (4) — sha1-based IDs are stable and unique.

### Stats
- Tests: 137 passing
- Ruff: 0 issues

### TODO (updated)
- **Connection pooling**: `api/db.py` still creates a new psycopg2 connection per request. Migrate to `psycopg2.pool.ThreadedConnectionPool` for production.
- **CORS restriction**: `middleware.py` allows `*` origins. Restrict to dashboard origin via `CORS_ORIGINS` env var.
- **Rate limiting per tenant**: key on `tenant_id` from JWT claims instead of IP.
- **LLM cancellation granularity**: `cancel_event` stops generation at next `yield`, not mid-computation. llama-cpp doesn't support interruption mid-token-compute.
- **`/health` Qdrant check**: `client.get_collections()` will be deprecated in future qdrant-client versions. Migrate to `client.info()` when the warning appears.
- **BM25 locks in-process only**: `_bm25_lock` is a Python dict — guards concurrent threads in one process. Multi-process (Gunicorn workers) would need a file lock (`fcntl.flock`).

## Shift Continuation — 2026-05-16 (Session 3)

### Bugs fixed
- `generation/streamer.py`: sync `generate_stream` generator iterated directly in async WS handler → blocked event loop per token. Fix: thread + `SimpleQueue` + `run_in_executor` pattern — event loop stays responsive during LLM inference.
- `dashboard/src/hooks/useStream.js`: no WebSocket cleanup on component unmount → connection leak. Fix: `useEffect(() => () => ws.close(), [])` teardown.
- `api/schemas.py`: `TenantCreate.slug` had `min_length=1` but regex `^[a-z0-9][a-z0-9-]*[a-z0-9]$` silently rejected single-char slugs. Fix: regex updated to `^[a-z0-9]([a-z0-9-]*[a-z0-9])?$`.
- `ingestion/parser.py`: `for _, row in enumerate(rows)` — index `_` unused. Fix: `for row in rows`.
- `api/main.py`: no warning when JWT_SECRET is default insecure value. Fix: startup warning log.

### New test files
- `tests/test_streamer.py` — 10 tests for `stream_rag_response` (no-chunks error, LLM unavailable error, successful token frames, done frame, result text, threading correctness, exception propagation).
- `tests/test_vector_store.py` — 11 tests for `VectorStore` (collection name, search result keys, dense_rank, error fallback, missing payload defaults, `collection_exists` delegation).

### Stats
- Tests: 126 passing (up from 105 at start of session)
- Ruff: 0 issues

### TODO for future sessions
- **Connection pooling**: `api/db.py` creates a new `psycopg2` connection per request. Migrate to `psycopg2.pool.ThreadedConnectionPool` or switch to async `asyncpg` for high-traffic deployments.
- **CORS restriction**: `middleware.py` allows `*` origins. Tighten to dashboard origin in production via `CORS_ORIGINS` env var.
- **Rate limiting per tenant**: `api/main.py` rate-limits by IP. Better: key on `tenant_id` from JWT claims to enforce per-tenant quotas.
- **BM25 rebuild on delete**: `delete_document_vectors` removes Qdrant points but does NOT rebuild the BM25 index — deleted doc texts remain in BM25. Needs a `_rebuild_bm25` that filters out deleted `doc_id` from the existing pickle.
- **Streaming test with real asyncio queue**: current `test_streamer.py` mocks at `HybridRetriever.retrieve` level. Add an end-to-end streaming test that exercises the thread+queue path with a generator that yields slowly.
- **`/health` Qdrant check**: `health.py` calls `client.get_collections()` (deprecated in qdrant-client 1.18+). Migrate to `client.get_aliases()` or just `client.info()`.

## Shift Continuation — 2026-05-16 (Session 2)
### Commits
- chore(lint): pyproject.toml with ruff, fixed 148 lint issues (138 auto + 10 manual)
- fix(reranker,scripts): reranker local-only KVKK fix, script cleanup (xlsx/csv support, SIM117)
- fix(indexer): conn leak in _update_postgres_status, dedup _TURKISH_STOPWORDS, add start/end_char to BM25 payload
- test(indexer): 9 unit tests for TenantIndexer (87 total tests now)
- fix(main): _init_postgres connection leak (conn.close in finally)
- refactor(streamer): dedup strip_think_tags import
- fix(ChatWindow): double-render bug on error messages
- cleanup(ingestion): dead `import re` in chunker, stale embedder docstring
- fix(docker,deps): Docker build context broken (parent dir COPY), add regex dep, remove asyncpg
- test(api): extension validation test with real JWT

### Bugs found and fixed
- reranker.py loaded from HuggingFace Hub (KVKK violation, same as embedder was)
- indexer._update_postgres_status: conn.close() not in finally → connection leak on error
- indexer._update_bm25: BM25 payloads missing start_char/end_char fields
- _TURKISH_STOPWORDS defined twice (indexer.py + bm25_store.py) — unified via import
- main._init_postgres: conn.close() not in finally → connection leak if schema SQL fails
- ChatWindow.jsx: error message rendered twice (once as plain text, once as error span)
- Docker: api/Dockerfile used `COPY ../` (parent directory, rejected by Docker) — fixed build context
- requirements.txt: regex package missing, asyncpg listed but unused
