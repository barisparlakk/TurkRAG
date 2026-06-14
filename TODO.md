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

## Current gaps

- [ ] Proper authentication/authorization: auth is still demo-only (`/auth/token` member minting + `/auth/mock-login` fixed credentials); production identity verification is still missing.
- [ ] Dashboard role-awareness is still tenant-scoped: admin flows can switch tenant context safely now, but there is still no real user directory or session-backed admin identity.

## Deferred work

- [ ] Tighten CORS defaults for non-local deployments once the canonical dashboard origin(s) are fixed per environment.
- [ ] Add an integration-level CORS header test against a minimal FastAPI app if API surface changes around middleware wiring.
- [ ] Fold retrieval-only metrics into `scripts/run_experiments.py` / `eval.ragas_eval.py` too if the report still needs a single end-to-end experiment artifact.
