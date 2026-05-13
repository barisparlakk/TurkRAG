FROM python:3.11-slim

WORKDIR /app

# System dependencies for pdfplumber, psycopg2, torch
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libpq-dev libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

COPY ../requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY .. /app

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
