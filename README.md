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

# 2. Start all services
docker compose up

# 3. Open the dashboard
open http://localhost:5173
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/token` | Issue a JWT for dev/testing |
| `GET` | `/health` | Health check (Qdrant, Postgres, LLM) |
| `POST` | `/documents/upload` | Upload PDF/DOCX/TXT/XLSX/CSV |
| `GET` | `/documents` | List tenant documents |
| `DELETE` | `/documents/{id}` | Delete document |
| `POST` | `/chat` | Synchronous RAG query |
| `WS` | `/chat/stream` | Streaming WebSocket RAG |
| `POST` | `/tenants` | Create tenant (admin) |
| `GET` | `/tenants` | List tenants (admin) |
| `DELETE` | `/tenants/{slug}` | Delete tenant + all data (admin) |
| `GET` | `/analytics/stats` | Query stats (totals, top queries, top docs) |
| `GET` | `/analytics/recent` | Recent query log entries |

Interactive docs at: http://localhost:8000/docs

---

## Provision a New Tenant

```bash
python scripts/create_tenant.py --name "Acme Şirketi" --slug "acme"
```

This creates the PostgreSQL row, provisions a Qdrant collection, and prints an admin JWT.

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

Metrics: `faithfulness`, `answer_relevancy`, `context_precision`, `context_recall`

Additional evaluation utilities already in the repo:

```bash
python scripts/run_experiments.py --tenant demo
python -m eval.retrieval_metrics --tenant demo
python -m eval.error_analysis --tenant demo
python scripts/plot_results.py
python scripts/generate_eval_set.py --tenant demo --max-chunks 20
```

### Evaluation Results

Recent generated artifacts in [`/Users/barisparlak/Desktop/TurkRAG/results`](/Users/barisparlak/Desktop/TurkRAG/results) and [`/Users/barisparlak/Desktop/TurkRAG/figures`](/Users/barisparlak/Desktop/TurkRAG/figures):

| Artifact | Purpose |
|----------|---------|
| `results/experiment_*.csv` | Multi-mode experiment summary from `scripts/run_experiments.py` |
| `results/*_hybrid*.json`, `results/*_dense.json`, `results/*_sparse.json` | Per-mode RAGAS run outputs |
| `results/retrieval_metrics*.json` | Retrieval-only metrics such as Recall@K, MRR, and nDCG |
| `figures/metrics_comparison.png` | RAGAS comparison chart across retrieval modes |
| `figures/recall_at_k.png` | Retrieval recall visualization |
| `figures/metrics_radar.png` | Radar overview of the main RAGAS metrics |

Run the commands above to refresh those artifacts for the current dataset or tenant.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_URL` | `postgresql://turkrag:turkrag_secret@localhost/turkrag` | PostgreSQL connection string |
| `LLM_MODEL_PATH` | `models/qwen3-8b-instruct-q4_k_m.gguf` | Path to GGUF model file |
| `LLM_N_CTX` | `4096` | LLM context window (tokens) |
| `LLM_N_GPU_LAYERS` | `-1` | GPU layers (-1 = all) |
| `LLM_N_THREADS` | `8` | CPU threads for prompt eval |
| `LLM_TEMPERATURE` | `0.1` | Sampling temperature |
| `LLM_MAX_TOKENS` | `512` | Max generated tokens per response |
| `TURKISH_EMBEDDER_PATH` | `models/turkish-embedder` | Local SentenceTransformer directory |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant vector DB URL |
| `JWT_SECRET` | *(required)* | Secret for signing JWTs |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins for the dashboard/API |
| `UPLOAD_DIR` | `/tmp/uploads` | Temporary file upload path |
| `BM25_INDEX_DIR` | `indexes` | BM25 index persistence directory |

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
