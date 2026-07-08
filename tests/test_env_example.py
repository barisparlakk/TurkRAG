"""Regression tests for the checked-in environment template."""

from pathlib import Path

EXPECTED_ENV_KEYS = {
    "APP_ENV",
    "ATTRIBUTION_MAX_SOURCES",
    "ATTRIBUTION_THRESHOLD",
    "AUTH_RATE_LIMIT",
    "AUTO_INIT_SCHEMA",
    "BM25_INDEX_DIR",
    "CACHE_THRESHOLD",
    "CACHE_TTL_SECONDS",
    "CHAT_RATE_LIMIT",
    "CORS_ORIGINS",
    "DB_POOL_MAX",
    "DB_POOL_MIN",
    "EMBEDDING_MODEL",
    "ENABLE_DEV_AUTH",
    "EVAL_FINAL_K",
    "EVAL_QUERIES_PATH",
    "EVAL_RATE_LIMIT",
    "EVAL_RETRIEVAL_MODE",
    "EVAL_STALE_JOB_TIMEOUT_SECONDS",
    "EVAL_TOP_K",
    "FOLLOWUP_ENABLED",
    "HEALTH_INCLUDE_DETAILS",
    "HYDE_ENABLED",
    "HYDE_MAX_TOKENS",
    "INGESTION_MAX_JOB_ATTEMPTS",
    "INGESTION_HEARTBEAT_INTERVAL_SECONDS",
    "INGESTION_RETRY_DELAY_SECONDS",
    "INGESTION_STALE_JOB_TIMEOUT_SECONDS",
    "JWT_SECRET",
    "LLM_MAX_TOKENS",
    "LLM_MODEL_PATH",
    "LLM_N_CTX",
    "LLM_N_GPU_LAYERS",
    "LLM_N_THREADS",
    "LLM_TEMPERATURE",
    "MAX_CSV_FIELD_SIZE",
    "MAX_PARSED_CHARS",
    "MAX_PDF_PAGES",
    "MAX_REQUEST_BODY_BYTES",
    "MAX_SPREADSHEET_CELLS",
    "MAX_SPREADSHEET_ROWS",
    "MAX_UPLOAD_BYTES",
    "MOCK_ADMIN_EMAIL",
    "MOCK_ADMIN_PASSWORD",
    "POSTGRES_PASSWORD",
    "POSTGRES_URL",
    "QDRANT_URL",
    "RATE_LIMIT",
    "REDIS_URL",
    "RERANKER_MODEL_PATH",
    "RERANK_CONFIDENCE_THRESHOLD",
    "TURKISH_EMBEDDER_PATH",
    "UPLOAD_DIR",
    "UPLOAD_RATE_LIMIT",
    "VITE_API_URL",
    "WS_RATE_LIMIT_PER_MINUTE",
}


def _parse_env_keys(path: Path) -> set[str]:
    keys = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        keys.add(stripped.split("=", 1)[0])
    return keys


def test_env_example_documents_current_runtime_configuration():
    keys = _parse_env_keys(Path(".env.example"))

    assert keys >= EXPECTED_ENV_KEYS
