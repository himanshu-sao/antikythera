# Antikythera Backend + Orchestrator
# Multi-stage build for production-ready image
ARG PYTHON_VERSION=3.9

# ------------------------------------------------------------------------------
# Stage 1: Builder - Install dependencies
# ------------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim as builder

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
FROM python:${PYTHON_VERSION}-slim as runtime

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
COPY automation-ideas/ ./automation-ideas/

# Create directories for logs
RUN mkdir -p /app/logs

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