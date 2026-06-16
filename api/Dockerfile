FROM python:3.11-slim

WORKDIR /app

# System dependencies for pdfplumber, psycopg2, torch
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libpq-dev libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system app && useradd --system --gid app --create-home appuser

COPY requirements.txt requirements.lock.txt /app/
RUN pip install --no-cache-dir -r requirements.txt -c requirements.lock.txt

COPY --chown=appuser:app . /app
RUN mkdir -p /tmp/uploads /app/indexes \
    && chown -R appuser:app /tmp/uploads /app/indexes

USER appuser

EXPOSE 8001
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
