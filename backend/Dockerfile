# ---------- Stage 1: build frontend ----------
FROM node:20-slim AS frontend-build

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ .
RUN npm run build


# ---------- Stage 2: backend + serve frontend ----------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install backend dependencies (pyproject.toml has no [build-system], install directly)
COPY backend/pyproject.toml .
RUN pip install --no-cache-dir \
      "fastapi>=0.115.0" \
      "uvicorn[standard]>=0.30.0" \
      "pydantic[email]>=2.8.0" \
      "chromadb>=0.5.0"

# Copy backend source
COPY backend/app/ app/

# Copy frontend dist into the path expected by main.py
#   main.py: DIST_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"
#   /app/app/main.py -> parents[0]=/app/app, parents[1]=/app, parents[2]=/
#   DIST_DIR = /frontend/dist
COPY --from=frontend-build /build/frontend/dist /frontend/dist

# Ollama / LLM defaults — override in docker-compose
ENV OLLAMA_BASE_URL=http://ollama:11434 \
    LOCAL_LLM_BASE_URL=http://ollama:11434/v1 \
    LOCAL_LLM_MODEL=qwen2.5:7b-instruct \
    LOCAL_LLM_MODELS=qwen2.5:7b-instruct,deepseek-r1:7b \
    LOCAL_LLM_TIMEOUT_SECONDS=300 \
    LOCAL_EMBED_MODEL=bge-m3:latest \
    LOCAL_EMBED_TIMEOUT_SECONDS=300

EXPOSE 8765

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8765", "--workers", "1"]
