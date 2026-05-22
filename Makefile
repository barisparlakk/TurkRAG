.PHONY: start stop restart logs status dev-api dev-ui infra

QDRANT_BIN := ./bin/qdrant

# ── Start all services ────────────────────────────────────────────────────────
start: infra
	@echo "Starting API..."
	@PYTHON=$$(command -v python3 || command -v python); \
	 if [ -f .venv/bin/python ]; then PYTHON=.venv/bin/python; fi; \
	 $$PYTHON -m uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload \
	 > /tmp/turkrag_api.log 2>&1 & echo $$! > /tmp/turkrag_api.pid
	@echo "Starting dashboard..."
	@cd dashboard && npm run dev > /tmp/turkrag_vite.log 2>&1 & echo $$! > /tmp/turkrag_vite.pid
	@sleep 2
	@$(MAKE) status

infra:
	@echo "Starting Qdrant..."
	@$(QDRANT_BIN) > /tmp/turkrag_qdrant.log 2>&1 & echo $$! > /tmp/turkrag_qdrant.pid
	@echo "Starting PostgreSQL (assumes local install)..."
	@pg_ctl start -D /usr/local/var/postgresql@14 -l /tmp/turkrag_pg.log 2>/dev/null || \
	 pg_ctl start -D /opt/homebrew/var/postgresql@14 -l /tmp/turkrag_pg.log 2>/dev/null || \
	 echo "  (PostgreSQL already running or managed externally)"
	@sleep 1

stop:
	@echo "Stopping services..."
	@cat /tmp/turkrag_api.pid 2>/dev/null | xargs kill 2>/dev/null || pkill -f "uvicorn api.main" 2>/dev/null || true
	@cat /tmp/turkrag_vite.pid 2>/dev/null | xargs kill 2>/dev/null || pkill -f "vite" 2>/dev/null || true
	@cat /tmp/turkrag_qdrant.pid 2>/dev/null | xargs kill 2>/dev/null || pkill -f "qdrant" 2>/dev/null || true
	@rm -f /tmp/turkrag_*.pid
	@# Force-clear ports so restart never hits EADDRINUSE
	@lsof -ti :8001 2>/dev/null | xargs kill -9 2>/dev/null || true
	@lsof -ti :5173 2>/dev/null | xargs kill -9 2>/dev/null || true
	@lsof -ti :6333 2>/dev/null | xargs kill -9 2>/dev/null || true
	@sleep 1
	@echo "All services stopped."

restart: stop
	@$(MAKE) start

status:
	@echo "=== TurkRAG Service Status ==="
	@lsof -i :8001 -sTCP:LISTEN >/dev/null 2>&1 && echo "  API        :8001  ✓" || echo "  API        :8001  ✗"
	@lsof -i :5173 -sTCP:LISTEN >/dev/null 2>&1 && echo "  Dashboard  :5173  ✓" || echo "  Dashboard  :5173  ✗"
	@lsof -i :6333 -sTCP:LISTEN >/dev/null 2>&1 && echo "  Qdrant     :6333  ✓" || echo "  Qdrant     :6333  ✗"
	@lsof -i :5432 -sTCP:LISTEN >/dev/null 2>&1 && echo "  Postgres   :5432  ✓" || echo "  Postgres   :5432  ✗"

logs:
	@echo "=== API ===" && tail -20 /tmp/turkrag_api.log 2>/dev/null
	@echo "=== Vite ===" && tail -10 /tmp/turkrag_vite.log 2>/dev/null
	@echo "=== Qdrant ===" && tail -10 /tmp/turkrag_qdrant.log 2>/dev/null

logs-api:
	@tail -f /tmp/turkrag_api.log

# ── Individual dev runners ────────────────────────────────────────────────────
dev-api:
	@PYTHON=$$(command -v python3 || command -v python); \
	 if [ -f .venv/bin/python ]; then PYTHON=.venv/bin/python; fi; \
	 $$PYTHON -m uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload

dev-ui:
	@cd dashboard && npm run dev
