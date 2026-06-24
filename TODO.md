# TurkRAG TODO

Last reviewed: 2026-06-24

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

- [x] Generated historical eval artifacts no longer contain model scratchpad text; shared sanitization now covers new eval outputs and the committed artifacts were rewritten.
- [x] `tests/test_middleware.py`: cover production CORS validation and a header-level middleware integration path so env drift is caught before deploys.
- [x] `api/db.py` and `tests/test_db.py`: make pooled connection release idempotent so duplicate cleanup cannot return one physical connection to the pool twice.
- [x] `api/routers/health.py` and `tests/test_health.py`: run dependency probes concurrently outside the event loop, close probe clients, and cover healthy/degraded responses without live services.
- [x] `eval/retrieval_metrics.py` and `tests/test_retrieval_metrics.py`: count each relevant document once so repeated chunks cannot push normalized retrieval metrics above 1.0.
- [x] `eval/ragas_eval.py`, `scripts/run_experiments.py`, and `scripts/plot_results.py`: compute, persist, export, and plot RAG/retrieval/latency metrics from one retrieval pass and one artifact set.
- [x] `eval/auto_eval.py`, `api/routers/evaluation.py`, and `dashboard/src/components/AdminPanel.jsx`: replace blocking API evaluation with an admin-only persisted background lifecycle, duplicate suppression, stale recovery, and UI polling.
- [x] `eval/auto_eval.py`, `api/routers/evaluation.py`, and `tests/test_evaluation_jobs.py`: add single-run status polling and conditional worker claiming so duplicate background invocations cannot re-run terminal evaluation jobs.
- [x] `api/main.py` and `tests/test_startup_schema.py`: accept both the legacy and renamed Alembic revision IDs so existing migrated databases keep starting after the local revision rename.
- [ ] Regenerate committed `results/retrieval_metrics*.json` artifacts against the live index; existing files contain inflated pre-fix metrics and should not be used for reporting.

## Deferred work

- [ ] Tighten CORS defaults for non-local deployments once the canonical dashboard origin(s) are fixed per environment.
