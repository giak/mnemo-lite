# syntax=docker/dockerfile:1.4
# Multi-stage build with BuildKit optimizations

# ============================================
# Stage 1: Builder (compilation)
# ============================================
FROM python:3.12-slim AS builder

WORKDIR /app

# Copy only requirements first (better caching)
COPY api/requirements.txt .

# Install build dependencies and build wheels with cache mount
RUN sed -i 's|http://deb.debian.org/debian|http://ftp.fr.debian.org/debian|g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
        python3-dev && \
    pip install --upgrade pip wheel setuptools && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Build wheels with BuildKit cache mount (OPTIMIZATION: 5-10× faster rebuilds)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip wheel --no-cache-dir --wheel-dir=/app/wheels -r requirements.txt

# ============================================
# Stage 2: Runtime (production)
# ============================================
FROM python:3.12-slim

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install runtime dependencies only
RUN sed -i 's|http://deb.debian.org/debian|http://ftp.fr.debian.org/debian|g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create appuser BEFORE copying files (OPTIMIZATION: better layer caching)
RUN useradd -m -u 1000 appuser

# Create necessary directories with correct ownership
RUN mkdir -p /app/logs /app/certs /app/scripts/database && \
    chown -R appuser:appuser /app

# Copy wheels from builder
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .

# Copy dev requirements
COPY requirements-dev.txt .

# Install dependencies from wheels with cache mount (OPTIMIZATION)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache --no-index --find-links=/wheels -r requirements.txt && \
    rm -rf /wheels

# Install dev requirements with cache mount (OPTIMIZATION)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache -r requirements-dev.txt

# Install linting tools with cache mount (OPTIMIZATION)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir black flake8 pylint autopep8

# Copy application code with correct ownership (OPTIMIZATION: COPY --chown)
COPY --chown=appuser:appuser api/ /app/api/

# Copy scripts with correct ownership (OPTIMIZATION: COPY --chown)
COPY --chown=appuser:appuser scripts/database/init_test_db.sql /app/scripts/database/init_test_db.sql

# Switch to non-root user
USER appuser

# Health check (commented - using docker-compose healthcheck instead)
# HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
#     CMD curl --fail http://localhost:8000/health || exit 1

# Run uvicorn with hot-reload for development
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
