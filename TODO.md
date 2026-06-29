# TurkRAG TODO

Last reviewed: 2026-06-29

## Requirement analysis

- [x] `TECHNICAL_ROADMAP.md`: reconcile the experiment phases with the current codebase; chunking/embedder/sweep scripts already exist and the documented outputs must match their real JSON artifacts.
- [x] `README.md`: document the `EMBEDDING_MODEL` experiment override alongside `TURKISH_EMBEDDER_PATH` so ablation scripts match the embedder contract.
- [x] `api/middleware.py`: support production-safe CORS configuration via `CORS_ORIGINS`.
- [x] `README.md`: align docs with the actual database driver (`psycopg2`, not `asyncpg`).
- [x] `README.md`: refresh the evaluation/results sections so they reflect the current implemented experiment scripts and outputs.
- [x] `TECHNICAL_ROADMAP.md`: reconcile stale items with the current codebase; several modules listed as "to be created" already exist.
- [x] `dashboard`: ignore generated `vite.config.js.timestamp-*.mjs` artifacts from the worktree.
- [x] `api/routers/tenants.py` and `dashboard/src/App.jsx`: review existing changes and remove the accidental public-admin escalation path.
- [x] `ingestion/chunker.py`: make `get_chunker("turkish", max_chars=..., overlap_chars=...)` apply experiment overrides instead of silently using defaults.
- [x] `eval/ragas_eval.py`, `scripts/run_experiments.py`, and `scripts/plot_results.py`: persist latency metrics so experiment artifacts can generate the advertised latency distribution plot.
- [x] `api/main.py` and `dashboard/src/api/client.js`: remove public caller-controlled admin role minting from `/auth/token`; use an authenticated admin tenant-switch endpoint instead.
- [x] `api/auth.py`, `api/main.py`, `api/routers/users.py`, and `dashboard`: add tenant-scoped local email/password login, active user validation, admin user management, and dev-auth gating.
- [x] `api/routers/sessions.py`, `api/routers/export.py`, and `api/routers/chat.py`: make sessions and exports user-aware while preserving admin tenant visibility.
- [x] `api/routers/documents.py` and `dashboard`: return ingestion `job_id`, track job states, expose job history, and show upload/job feedback in the UI.
- [x] `eval/ragas_eval.py`, `eval/auto_eval.py`, `api/routers/evaluation.py`, and `scripts/run_experiments.py`: align `eval_runs` persistence and include retrieval-only metrics in experiments.
- [x] `api/middleware.py`, `api/routers/health.py`, and `README.md`: add production safety checks for JWT/CORS and richer health details.
- [x] `api/rbac.py`, `api/routers/documents.py`, `api/routers/permissions.py`, `api/routers/chat.py`, `generation/streamer.py`, and `retrieval/semantic_cache.py`: enforce document ACLs for new documents in listing/retrieval/chat, scope cached answers per user, and restrict permission management to owners/admins.
- [x] `migrations/versions/0003_backfill_document_permissions.py` and `scripts/backfill_document_permissions.py`: backfill ACL rows for legacy documents by granting active tenant admins owner access and active members viewer access.
- [x] `scripts/bootstrap_admin.py`, `tests/test_bootstrap_admin.py`, and `README.md`: add an idempotent first-admin bootstrap path for existing tenants before disabling dev auth in production.
- [x] `tests/test_experiment_scripts.py`: add lightweight CLI coverage for `chunking_experiments`, `embedder_experiments`, and `hyperparameter_sweep` so roadmap/script drift is caught automatically.

## Current gaps

- [x] `dashboard/src/App.jsx`, dashboard components, and `dashboard/src/index.css`: complete a full SaaS-style frontend redesign covering shell navigation, chat, source panel, document operations, analytics/admin surfaces, light/dark themes, and responsive layouts while preserving API contracts.
- [x] `dashboard/src/components/ChatWindow.jsx`, `DocumentUpload.jsx`, `SourcesPanel.jsx`, `Sidebar.jsx`, and `index.css`: replace the generic SaaS hero/dashboard look with a TurkRAG-specific document intelligence workbench, evidence panel, ingestion pipeline, dense session rail, and sharper Turkish ops visual language.
- [x] `dashboard/src/components/AnalyticsDashboard.jsx`, `AdminPanel.jsx`, `ChatWindow.jsx`, `Sidebar.jsx`, and `index.css`: perform a full design-audit-driven UI/UX refinement so the dashboard reads as a coherent Turkish institutional evidence desk instead of a generic AI/SaaS interface.
- [x] `dashboard/src/components/ChatWindow.jsx` and `dashboard/src/index.css`: correct the over-dark evidence-desk direction by making the chat UX composer-first, improving the evidence/scope flow, and replacing the muddy color treatment with a cleaner premium enterprise palette.
- [x] `dashboard/src/index.css`: remove the pale yellow/cream palette and replace it with a cleaner neutral white/slate color system with controlled teal and copper accents.
- [x] `dashboard/src/components/ChatWindow.jsx` and `dashboard/src/index.css`: reduce the empty chat hero treatment into a compact query workbench, with scope pills and dense workflow rows instead of large generic prompt cards.
- [x] `api/routers/dashboard.py`, `api/routers/collections.py`, `api/routers/settings.py`, `api/routers/documents.py`, `dashboard/src/App.jsx`, `dashboard/src/components/OperationsPages.jsx`, `Sidebar.jsx`, `Header.jsx`, `ChatWindow.jsx`, and `dashboard/src/index.css`: implement the reference-inspired dark enterprise AI console with backend-backed dashboard summary, collections, UI settings, document metadata, ingestion jobs, history, analytics, system status, and responsive sidebar/topbar navigation.
- [x] `api/db.py`, `tests/test_db.py`, and `README.md`: make PostgreSQL pool sizing configurable via env vars and fail fast on invalid min/max settings instead of hardcoding a single 2-10 range.
- [x] `scripts/repair_retrieval_artifacts.py`: defer project imports until runtime so the artifact-repair CLI remains importable in tests but also passes `ruff` without module-level import-order violations.
- [x] `scripts/audit_retrieval_artifacts.py` and `tests/test_eval_artifacts.py`: add a deterministic audit for committed `results/retrieval_metrics*.json` files so out-of-range normalized metrics, blank questions, and filename/query-count drift are caught before those artifacts are reused.
- [x] Generated historical eval artifacts no longer contain model scratchpad text; shared sanitization now covers new eval outputs and the committed artifacts were rewritten.
- [x] `tests/test_middleware.py`: cover production CORS validation and a header-level middleware integration path so env drift is caught before deploys.
- [x] `api/db.py` and `tests/test_db.py`: make pooled connection release idempotent so duplicate cleanup cannot return one physical connection to the pool twice.
- [x] `api/routers/health.py` and `tests/test_health.py`: run dependency probes concurrently outside the event loop, close probe clients, and cover healthy/degraded responses without live services.
- [x] `eval/retrieval_metrics.py` and `tests/test_retrieval_metrics.py`: count each relevant document once so repeated chunks cannot push normalized retrieval metrics above 1.0.
- [x] `eval/ragas_eval.py`, `scripts/run_experiments.py`, and `scripts/plot_results.py`: compute, persist, export, and plot RAG/retrieval/latency metrics from one retrieval pass and one artifact set.
- [x] `eval/auto_eval.py`, `api/routers/evaluation.py`, and `dashboard/src/components/AdminPanel.jsx`: replace blocking API evaluation with an admin-only persisted background lifecycle, duplicate suppression, stale recovery, and UI polling.
- [x] `eval/auto_eval.py`, `api/routers/evaluation.py`, and `tests/test_evaluation_jobs.py`: add single-run status polling and conditional worker claiming so duplicate background invocations cannot re-run terminal evaluation jobs.
- [x] `api/main.py` and `tests/test_startup_schema.py`: accept both the legacy and renamed Alembic revision IDs so existing migrated databases keep starting after the local revision rename.
- [x] `scripts/repair_retrieval_artifacts.py`, `scripts/repair_generated_eval_csv.py`, committed eval/results artifacts, and focused tests: restore blank generated-eval questions from the fuller CSV export, recompute duplicate-safe normalized metrics from stored `retrieved_docs`/`relevant_docs`, rewrite the stale committed artifacts in place, and gate them with `python scripts/audit_retrieval_artifacts.py`.
- [x] `generation/streamer.py`, `generation/attribution.py`, `tests/test_streamer.py`, and `tests/test_attribution.py`: make post-answer attribution/follow-up worker failures exception-safe so streaming responses cannot hang after the `done` frame, and keep low-confidence fallback source metadata consistent.
- [x] `api/routers/documents.py` and `tests/test_documents.py`: make ingestion job status/history enforce document ACLs for tenant members while preserving tenant-admin visibility.
- [x] `api/routers/documents.py` and `tests/test_documents.py`: reject upload requests with path-only or extension-only filenames before writing temporary files or opening DB connections.

## Deferred work

- [ ] Tighten CORS defaults for non-local deployments once the canonical dashboard origin(s) are fixed per environment.
- [ ] Re-run `python -m eval.retrieval_metrics --tenant <slug>` against a live indexed tenant when fresh historical retrieval baselines are needed; the repaired committed JSONs now have valid normalized metrics, but they still reflect the original ranked retrieval snapshots.
