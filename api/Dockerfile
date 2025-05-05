# Multi-stage build
FROM python:3.12-slim as builder

# Set working directory
WORKDIR /app

# Copy requirements file
COPY api/requirements.txt .

# Install build dependencies
RUN sed -i 's|http://deb.debian.org/debian|http://ftp.fr.debian.org/debian|g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    python3-dev && \
    pip install --upgrade pip wheel setuptools && \
    pip wheel --no-cache-dir --wheel-dir=/app/wheels -r requirements.txt && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Runtime stage
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install runtime dependencies
RUN sed -i 's|http://deb.debian.org/debian|http://ftp.fr.debian.org/debian|g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels from builder stage
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .
COPY requirements-dev.txt .

# Install dependencies from wheels using requirements.txt
RUN pip install --no-cache --no-index --find-links=/wheels -r requirements.txt
# Install dev requirements separately
RUN pip install --no-cache -r requirements-dev.txt

# Copy application code - Ensure it goes into an /app/api subdirectory
COPY api/ /app/api/

# Create necessary directories
RUN mkdir -p /app/logs /app/certs

# Add non-root user
RUN useradd -m appuser && \
    chown -R appuser:appuser /app
USER appuser

# Health check (COMMENTED OUT to rely only on docker-compose healthcheck)
# HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
#     CMD curl --fail http://localhost:8000/v1/health || exit 1

# Run the API server directly (Restore reload)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]