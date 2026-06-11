# TurkRAG TODO

Last reviewed: 2026-06-11

## Requirement analysis

- [x] `api/middleware.py`: support production-safe CORS configuration via `CORS_ORIGINS`.
- [x] `README.md`: align docs with the actual database driver (`psycopg2`, not `asyncpg`).
- [x] `README.md`: refresh the evaluation/results sections so they reflect the current implemented experiment scripts and outputs.
- [x] `TECHNICAL_ROADMAP.md`: reconcile stale items with the current codebase; several modules listed as "to be created" already exist.
- [x] `dashboard`: ignore generated `vite.config.js.timestamp-*.mjs` artifacts from the worktree.
- [x] `api/routers/tenants.py` and `dashboard/src/App.jsx`: review existing changes and remove the accidental public-admin escalation path.
- [x] `ingestion/chunker.py`: make `get_chunker("turkish", max_chars=..., overlap_chars=...)` apply experiment overrides instead of silently using defaults.
- [x] `eval/ragas_eval.py`, `scripts/run_experiments.py`, and `scripts/plot_results.py`: persist latency metrics so experiment artifacts can generate the advertised latency distribution plot.

## Current gaps

- [ ] Proper authentication/authorization: `/auth/token` is still a dev convenience endpoint that trusts caller-supplied roles; production auth is still missing.
- [ ] Dashboard role-awareness is minimal: admin-only views are hidden for member tokens, but there is still no first-class authenticated admin flow.

## Deferred work

- [ ] Tighten CORS defaults for non-local deployments once the canonical dashboard origin(s) are fixed per environment.
- [ ] Add an integration-level CORS header test against a minimal FastAPI app if API surface changes around middleware wiring.
- [ ] Fold retrieval-only metrics into `scripts/run_experiments.py` / `eval.ragas_eval.py` too if the report still needs a single end-to-end experiment artifact.
