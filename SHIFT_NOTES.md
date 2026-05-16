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
## Shift End
- Completed: session mgmt + analytics backend, Excel/CSV ingestion, api/db.py extraction, generation history/session_id, parallel retrieval, dashboard analytics tab + new chat, chunker spec keys, offline-only embedder, 35 tests (chunker/hybrid/API), test cleanup (parametrize), docs/architecture.md, README updates
- Remaining: nothing from priority list
- Decisions made: embedder raises on missing path (no HF fallback); character-based chunking kept (avoids tokenizer dep); psycopg2 kept over asyncpg (simplicity); connection pooling deferred (would need psycopg2.pool or asyncpg migration, out of scope)
- Review before push: api/db.py is new shared module — verify all callers import get_conn correctly; sessions table uses gen_random_uuid() via RETURNING — requires pg13+
