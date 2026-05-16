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
# SHIFT CHECKPOINT: completed [session mgmt, analytics, Excel/CSV, code cleanup, dashboard], next up [fix chunker return keys, fix embedder HuggingFace fallback, write tests]
