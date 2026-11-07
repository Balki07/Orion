# ==============================================================================
# Multi-stage Dockerfile for ORION Backend
# ==============================================================================

# Stage 1: Build & Dependencies
FROM python:3.11-slim AS builder

WORKDIR /build

# System build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV FASTEMBED_CACHE_DIR=/opt/fastembed_cache

# Install application dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Pre-download local FastEmbed ONNX model at build time
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5', cache_dir='/opt/fastembed_cache')"

# Stage 2: Production Runtime
FROM python:3.11-slim AS runner

WORKDIR /app

# Install runtime tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged application user
RUN useradd -m -u 1000 -s /bin/bash orion && \
    mkdir -p /app/storage/uploads /opt/fastembed_cache && \
    chown -R orion:orion /app /opt/fastembed_cache

# Copy python packages and pre-cached FastEmbed ONNX models from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder --chown=orion:orion /opt/fastembed_cache /opt/fastembed_cache

# Copy backend source code
COPY --chown=orion:orion app/ ./app/
COPY --chown=orion:orion migrations/ ./migrations/
COPY --chown=orion:orion alembic.ini ./

USER orion

ENV PYTHONUNBUFFERED=1
ENV FASTEMBED_CACHE_DIR=/opt/fastembed_cache
ENV ONNX_NUM_THREADS=1
ENV EMBEDDING_DEVICE=cpu
ENV ORION_ENV=production
ENV BACKEND_HOST=0.0.0.0
ENV BACKEND_PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
