# Antikythera Backend + Orchestrator
# Multi-stage build for production-ready image
ARG PYTHON_VERSION=3.12

# ------------------------------------------------------------------------------
# Stage 1: Builder - Install dependencies
# ------------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ------------------------------------------------------------------------------
# Stage 2: Runtime - Minimal image with entrypoint
# ------------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

# Ensure scripts in PATH
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY api/ ./api/
COPY agents/ ./agents/
COPY scripts/ ./scripts/

# agents/refiner.py, architect.py and tester.py build an LLMClient from config.yaml at
# import time, so the orchestrator cannot start without it (P0-8). It holds provider and
# model names plus the NAMES of env vars for keys, never secret values.
COPY config.yaml ./config.yaml

# Data directory is an empty mount point: real state (pipeline, vault, integrations)
# is bind-mounted or volume-mounted at run time and must never be baked into the image.
# Local data is excluded from the build context by /.dockerignore (SEC-14); never add a
# COPY of automation-ideas/ here.
RUN mkdir -p /app/automation-ideas /app/logs

# Copy entrypoint script
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Expose backend port
EXPOSE 8006

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8006/ || exit 1

# Entrypoint handles config validation and starts services
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Default command: start uvicorn (can be overridden in compose)
CMD ["--start-backend"]