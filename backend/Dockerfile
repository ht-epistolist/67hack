# syntax=docker/dockerfile:1
# Build context is the REPO ROOT (set source_dir: / + dockerfile_path: backend/Dockerfile
# in the App Platform spec) so we can also copy the dataset CSVs that live in /data.
FROM python:3.13-slim

# Native build deps a few wheels want (kuzu, lancedb, onnxruntime via fastembed).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential git curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first so this layer caches across app-code changes.
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# App code + the CSV datasets. config.py resolves the data dir as
# <repo_root>/data, i.e. /app/data here.
COPY backend/ ./backend/
COPY data/ ./data/

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend

WORKDIR /app/backend

# App Platform injects $PORT (defaults to 8080); bind uvicorn to it.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
