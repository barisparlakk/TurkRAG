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
