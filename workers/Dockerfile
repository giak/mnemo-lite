# Multi-stage build
FROM python:3.12-slim AS builder

WORKDIR /build
COPY workers/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.12-slim AS runtime

# Optimisations Python
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

WORKDIR /app
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Optimisation des couches
COPY ./workers/ingestion.py /app/
COPY ./workers/utils/ /app/utils/

# Création des répertoires nécessaires
RUN mkdir -p /app/data /app/config \
    && useradd -m appuser \
    && chown -R appuser:appuser /app

# Utilisation d'un utilisateur non-root
USER appuser

# Healthcheck pour s'assurer que le worker fonctionne
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD ps aux | grep ingestion.py | grep -v grep || exit 1

CMD ["python", "ingestion.py"] 