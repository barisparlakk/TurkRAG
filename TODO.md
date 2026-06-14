# TurkRAG TODO

Last reviewed: 2026-06-14

## Requirement analysis

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

## Current gaps

- [ ] Document-level permissions are still not enforced in retrieval/listing/chat; current access model is tenant-level member access plus admin controls.
- [ ] Existing deployments need a one-time admin bootstrap before disabling dev auth in production.
- [ ] Generated historical eval artifacts may still contain model scratchpad text; newly generated artifacts are cleaned, but old committed artifacts were not rewritten.

## Deferred work

- [ ] Tighten CORS defaults for non-local deployments once the canonical dashboard origin(s) are fixed per environment.
- [ ] Add an integration-level CORS header test against a minimal FastAPI app if API surface changes around middleware wiring.
- [ ] Fold retrieval-only metrics into `scripts/run_experiments.py` / `eval.ragas_eval.py` too if the report still needs a single end-to-end experiment artifact.
