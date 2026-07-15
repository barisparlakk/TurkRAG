# TurkRAG

> Privacy-first, on-premise RAG for Turkish enterprise

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110-green?logo=fastapi)
![React](https://img.shields.io/badge/React-18-61dafb?logo=react)
![Qdrant](https://img.shields.io/badge/Qdrant-vector--db-red)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

Companies upload their own documents and chat with an AI that answers **only from those documents** — fully on-premise, KVKK-compliant, in Turkish.

---

## Architecture

```
                  ┌──────────────┐
   PDF/DOCX/TXT → │  Ingestion   │
                  │  parser      │  PDF/DOCX/TXT/XLSX/CSV
                  │  chunker     │  Turkish-aware sentence chunker
                  │  embedder    │  local SentenceTransformer (offline)
                  │  indexer     │
                  └──────┬───────┘
                         │
              ┌──────────┴──────────┐
              │                     │
         ┌────▼────┐          ┌─────▼─────┐
         │  Qdrant │          │   BM25s   │
         │  (dense)│          │  (sparse) │
         └────┬────┘          └─────┬─────┘
              │                     │
              └──────────┬──────────┘
                         │  RRF Fusion
                  ┌──────▼──────┐
                  │  Re-ranker  │  ms-marco-MiniLM-L-6-v2
                  └──────┬──────┘
                         │
                  ┌──────▼──────┐
                  │ Generation  │  Qwen3-8B-Instruct (GGUF)
                  │  Turkish    │  System prompt + citations
                  │  prompt     │
                  └──────┬──────┘
                         │
                  ┌──────▼──────┐
                  │  FastAPI    │  REST + WebSocket streaming
                  │  + JWT auth │  Multi-tenant isolation
                  └──────┬──────┘
                         │
                  ┌──────▼──────┐
                  │   React     │  Streaming chat UI
                  │  Dashboard  │  Document upload + citations
                  └─────────────┘
```

---

## Quick Start

```bash
# 1. Download the LLM model (4.5 GB)
pip install huggingface-hub
huggingface-cli download Qwen/Qwen3-8B-Instruct-GGUF \
  qwen3-8b-instruct-q4_k_m.gguf --local-dir ./models

# 2. Configure required secrets
cp .env.example .env
# Edit JWT_SECRET and POSTGRES_PASSWORD in .env before production use.

# 3. Start Postgres/Qdrant, run migrations, then start all services
docker compose up -d postgres qdrant
docker compose run --rm api alembic upgrade head
docker compose up

# 4. Open the dashboard
open http://localhost:5173
```

For local development with Postgres and Qdrant exposed on host ports and automatic
schema initialization:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/login` | Login with tenant slug, email, and password |
| `POST` | `/auth/token` | Issue a dev JWT when `ENABLE_DEV_AUTH=true` |
| `GET` | `/users` | List tenant users (admin) |
| `POST` | `/users` | Create tenant user (admin) |
| `PATCH` | `/users/{id}` | Update user role/status (admin) |
| `GET` | `/health` | Health check (Qdrant, Postgres, Redis/cache, worker, LLM) |
| `GET` | `/dashboard/summary` | Tenant dashboard summary for documents, collections, query activity, evaluations, and recent ingestion activity |
| `POST` | `/documents/upload` | Upload PDF/DOCX/TXT/XLSX/CSV |
| `GET` | `/documents` | List tenant documents |
| `DELETE` | `/documents/{id}` | Delete document |
| `GET` | `/documents/jobs` | List ingestion jobs |
| `GET` | `/documents/jobs/{id}` | Check ingestion job status |
| `GET` | `/collections` | List tenant collections with ACL-aware document counts |
| `POST` | `/collections` | Create a tenant collection (admin) |
| `PATCH` | `/collections/{id}` | Update collection metadata (admin) |
| `DELETE` | `/collections/{id}` | Delete a collection without deleting documents (admin) |
| `POST` | `/collections/{id}/documents/{doc_id}` | Assign a manageable document to a collection |
| `POST` | `/chat` | Synchronous RAG query |
| `WS` | `/chat/stream` | Streaming WebSocket RAG |
| `POST` | `/tenants` | Create tenant (admin) |
| `GET` | `/tenants` | List tenants (admin) |
| `DELETE` | `/tenants/{slug}` | Delete tenant + all data (admin) |
| `GET` | `/analytics/stats` | Query stats (totals, top queries, top docs) |
| `GET` | `/analytics/recent` | Recent query log entries |
| `POST` | `/eval/run` | Queue one background evaluation for the tenant (admin, returns `202`) |
| `GET` | `/eval/history` | List queued/running/completed/failed evaluations (admin) |
| `GET` | `/eval/runs/{id}` | Fetch one evaluation run for focused status polling (admin) |
| `GET` | `/settings/ui` | Read tenant UI preferences |
| `PUT` | `/settings/ui` | Save safe tenant UI preferences |

Interactive docs at: http://localhost:8000/docs

---

## Provision a New Tenant

```bash
python scripts/create_tenant.py \
  --name "Acme Şirketi" \
  --slug "acme" \
  --admin-email "admin@acme.com" \
  --admin-password "change-me-strongly"
```

This creates the PostgreSQL row, provisions a Qdrant collection, and bootstraps the first admin user.

For existing deployments that already have tenants but still need their first
local admin before turning off dev auth:

```bash
python scripts/bootstrap_admin.py \
  --tenant-slug "acme" \
  --email "admin@acme.com" \
  --password "change-me-strongly"
```

The command is idempotent: it creates the tenant admin if missing, or
promotes/reactivates the existing tenant user and rotates its password hash.

---

## Ingest Sample Documents

```bash
# Ingest the 3 included Turkish sample documents under the 'demo' tenant
python scripts/ingest_demo.py --tenant demo
```

Sample files in `data/sample/`:
- `sirket_politikasi.txt` — company HR policy (working hours, leave, remote work)
- `urun_katalogu.txt` — product catalogue
- `musteri_hizmetleri.txt` — customer service FAQ

---

## Embedding Model Setup

The embedder **never downloads from HuggingFace Hub at runtime**. You must place a SentenceTransformer checkpoint locally before starting the API.

```bash
# Option A: download the base multilingual model (offline after first pull)
pip install sentence-transformers
python -c "
from sentence_transformers import SentenceTransformer
m = SentenceTransformer('sentence-transformers/paraphrase-multilingual-mpnet-base-v2')
m.save('models/turkish-embedder')
"

# Option B: fine-tune on Turkish NLI data (Google Colab A100 recommended)
# See TURKRAG_SETUP_GUIDE.md for the full training notebook.
# After training, copy the checkpoint:
cp -r /path/to/checkpoint models/turkish-embedder
```

Set `TURKISH_EMBEDDER_PATH` env var to override the default `models/turkish-embedder` path.

---

## Evaluation

```bash
python -m eval.ragas_eval --tenant demo
```

Each query is retrieved once. That ranked result is used for:

- RAG quality: `faithfulness`, `answer_relevancy`, `context_precision`, `context_recall`
- Retrieval quality: `mean_mrr`, `mean_ap`, `recall@1/3/5`, `ndcg@1/3/5`
- Performance: retrieval, generation, and total latency

`eval.ragas_eval` persists the complete metric and per-query payload to `eval_runs`. The multi-mode
runner exports the same payload to per-mode JSON and a combined CSV, so `plot_results.py` can build
metric, Recall@K, and latency figures without a second retrieval run.

The dashboard/API path uses the same evaluator as a persisted background job. Only one queued or
running evaluation is allowed per tenant; the admin panel polls until completion and displays stored
failure details. If the API process stops mid-run, the next trigger marks jobs older than
`EVAL_STALE_JOB_TIMEOUT_SECONDS` as failed before accepting a replacement. Workers claim queued
rows before execution, so duplicate background invocations cannot re-run a completed or failed job.

Additional evaluation utilities already in the repo:

```bash
python scripts/run_experiments.py --tenant demo
python -m eval.retrieval_metrics --tenant demo
python -m eval.error_analysis --tenant demo
python scripts/plot_results.py
python scripts/generate_eval_set.py --tenant demo --max-chunks 20
python scripts/chunking_experiments.py --tenant demo
python scripts/embedder_experiments.py --tenant demo
python scripts/hyperparameter_sweep.py --tenant demo
```

### Evaluation Results

Recent generated artifacts in [`/Users/barisparlak/Desktop/TurkRAG/results`](/Users/barisparlak/Desktop/TurkRAG/results) and [`/Users/barisparlak/Desktop/TurkRAG/figures`](/Users/barisparlak/Desktop/TurkRAG/figures):

| Artifact | Purpose |
|----------|---------|
| `results/experiment_*.csv` | Unified RAG, retrieval, and latency summary from `scripts/run_experiments.py` |
| `results/*_hybrid*.json`, `results/*_dense.json`, `results/*_sparse.json` | Complete per-mode metrics and per-query evidence |
| `results/retrieval_metrics*.json` | Retrieval-only metrics such as Recall@K, MRR, and nDCG |
| `results/chunking_experiments.json` | Chunker ablation summary across temporary tenant indexes |
| `results/embedder_experiments.json` | Dense-retrieval embedder comparison across local model directories |
| `results/hyperparameter_sweep.json` | Hyperparameter sweep results plus the top-scoring configurations |
| `figures/metrics_comparison.png` | RAGAS comparison chart across retrieval modes |
| `figures/recall_at_k.png` | Retrieval recall visualization |
| `figures/metrics_radar.png` | Radar overview of the main RAGAS metrics |

Run the commands above to refresh those artifacts for the current dataset or tenant.
The committed `results/retrieval_metrics*.json` files have been repaired to use duplicate-safe
normalized metrics derived from their stored ranked retrieval snapshots.
Use `python scripts/repair_retrieval_artifacts.py` to rewrite legacy retrieval artifacts in place,
then `python scripts/audit_retrieval_artifacts.py` to verify they stay within normalized metric
bounds and still match their declared query counts.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_URL` | `postgresql://turkrag:turkrag_secret@localhost/turkrag` | PostgreSQL connection string |
| `DB_POOL_MIN` | `2` | Minimum psycopg2 pooled PostgreSQL connections; must be `>= 1` and `<= DB_POOL_MAX` |
| `DB_POOL_MAX` | `10` | Maximum psycopg2 pooled PostgreSQL connections; must be `>= DB_POOL_MIN` |
| `LLM_MODEL_PATH` | `models/qwen3-8b-instruct-q4_k_m.gguf` | Path to GGUF model file |
| `LLM_N_CTX` | `4096` | LLM context window (tokens) |
| `LLM_N_GPU_LAYERS` | `-1` | GPU layers (-1 = all) |
| `LLM_N_THREADS` | `8` | CPU threads for prompt eval |
| `LLM_TEMPERATURE` | `0.1` | Sampling temperature |
| `LLM_MAX_TOKENS` | `512` | Max generated tokens per response |
| `TURKISH_EMBEDDER_PATH` | `models/turkish-embedder` | Local SentenceTransformer directory |
| `EMBEDDING_MODEL` | *(empty)* | Optional experiment-time local model path/name used by ablation scripts; falls back to `TURKISH_EMBEDDER_PATH` |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant vector DB URL |
| `JWT_SECRET` | *(required)* | Secret for signing JWTs |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins for the dashboard/API. `*` is rejected in production |
| `APP_ENV` | `production` in Docker, `development` locally | Production rejects insecure defaults |
| `ENABLE_DEV_AUTH` | `false` | Enable legacy dev token/mock login endpoints only for explicit local development |
| `AUTO_INIT_SCHEMA` | `false` | Local-only option to run `alembic upgrade head` during API startup. Rejected in production |
| `MOCK_ADMIN_EMAIL` / `MOCK_ADMIN_PASSWORD` | *(empty)* | Local-only mock admin credentials when dev auth is explicitly enabled |
| `UPLOAD_DIR` | `/tmp/uploads` | Temporary file upload path |
| `MAX_UPLOAD_BYTES` | `52428800` | Maximum upload size in bytes (default 50 MB) |
| `INGESTION_MAX_JOB_ATTEMPTS` | `3` | Maximum attempts before an ingestion job is marked failed |
| `INGESTION_RETRY_DELAY_SECONDS` | `60` | Delay before retrying a failed ingestion attempt |
| `INGESTION_STALE_JOB_TIMEOUT_SECONDS` | `900` | Processing heartbeat timeout before a job is recovered |
| `INGESTION_POLL_INTERVAL_SECONDS` | `5` | Delay between ingestion worker queue polls when no job is available |
| `INGESTION_HEARTBEAT_INTERVAL_SECONDS` | `30` | Interval for refreshing the active ingestion job heartbeat |
| `EVAL_QUERIES_PATH` | `eval/test_queries.json` | Ground-truth query set used by API-triggered evaluations |
| `EVAL_RETRIEVAL_MODE` | `hybrid+rerank` | Retrieval mode used by API-triggered evaluations |
| `EVAL_TOP_K` / `EVAL_FINAL_K` | `20` / `5` | Candidate and answer-context depth for API evaluations |
| `EVAL_STALE_JOB_TIMEOUT_SECONDS` | `3600` | Age after which an abandoned queued/running eval is failed on the next trigger |
| `BM25_INDEX_DIR` | `indexes` | BM25 index persistence directory |

---

## Database Migrations

TurkRAG uses Alembic for PostgreSQL schema management. API startup verifies that
the database is migrated to the required revision and fails fast if the schema is
missing or stale.

```bash
alembic upgrade head
```

For an existing database that already exactly matches the current schema, stamp
it once instead of recreating tables:

```bash
alembic stamp head
```

For a pre-Alembic database that matches only the original baseline tables, stamp
the baseline first and then apply later migrations:

```bash
alembic stamp 0001_baseline
alembic upgrade head
```

Migration `0003_acl_backfill` backfills ACL rows for legacy
documents that existed before document-level permissions. If you bootstrap users
after that migration has already run, rerun the idempotent backfill manually:

```bash
python scripts/backfill_document_permissions.py --dry-run
python scripts/backfill_document_permissions.py
```

`AUTO_INIT_SCHEMA=true` is available only for local development and is rejected
when `APP_ENV=production`.

---

## Production Hardening

The API and dashboard Docker images run as non-root users. Runtime write paths
used by the API are limited to `/tmp/uploads` and `/app/indexes`; mount writable
volumes there if overriding Compose defaults.

Python installs use `requirements.txt` with `requirements.lock.txt` constraints
in CI and Docker builds. Update `requirements.txt` for intended dependency
changes, then refresh the lock file from a verified environment.

---

## KVKK Compliance

- All data stays on the customer's server (on-premise Docker)
- No telemetry sent to external services
- Document storage paths are configurable via environment variables
- User data is minimal — no behavioural tracking
- Secrets are env vars (never hardcoded)
- Full data purge: `DELETE /tenants/{slug}` removes all documents, vectors, and metadata

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Qwen3-8B-Instruct GGUF (llama-cpp-python) |
| Embeddings | Local SentenceTransformer (offline, see setup) |
| Vector DB | Qdrant |
| Sparse index | BM25s |
| Reranker | ms-marco-MiniLM-L-6-v2 |
| API | FastAPI + psycopg2 |
| Database | PostgreSQL 16 |
| Frontend | React 18 + Vite |
| Evaluation | RAGAS |
