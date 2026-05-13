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
                  │  parser      │
                  │  chunker     │  Turkish-aware sentence chunker
                  │  embedder    │  multilingual-mpnet-base-v2
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
| `POST` | `/documents/upload` | Upload PDF/DOCX/TXT |
| `GET` | `/documents` | List tenant documents |
| `DELETE` | `/documents/{id}` | Delete document |
| `POST` | `/chat` | Synchronous RAG query |
| `WS` | `/chat/stream` | Streaming WebSocket RAG |
| `POST` | `/tenants` | Create tenant (admin) |
| `GET` | `/tenants` | List tenants (admin) |
| `DELETE` | `/tenants/{slug}` | Delete tenant + all data (admin) |

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

## Fine-tune the Turkish Embedding Model

Use Google Colab (A100) with the `nli_tr` dataset. See `TURKRAG_SETUP_GUIDE.md` for the full notebook.

```bash
# After training, copy checkpoint to:
models/turkish-embedder/
# The embedder auto-loads this if present.
```

---

## Evaluation

```bash
python -m eval.ragas_eval --tenant demo
```

Metrics: `faithfulness`, `answer_relevancy`, `context_precision`, `context_recall`

### Evaluation Results

| Metric | Score |
|--------|-------|
| Faithfulness | — |
| Answer Relevancy | — |
| Context Precision | — |
| Context Recall | — |

*Run the evaluation pipeline to populate this table.*

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
| Embeddings | paraphrase-multilingual-mpnet-base-v2 |
| Vector DB | Qdrant |
| Sparse index | BM25s |
| Reranker | ms-marco-MiniLM-L-6-v2 |
| API | FastAPI + asyncpg |
| Database | PostgreSQL 16 |
| Frontend | React 18 + Vite |
| Evaluation | RAGAS |
