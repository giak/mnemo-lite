# Multi-stage build
FROM python:3.12-slim AS builder

WORKDIR /build
COPY api/requirements.txt .
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
COPY ./api/models/ /app/models/
COPY ./api/routes/ /app/routes/
COPY ./api/main.py /app/

# Création des répertoires nécessaires
RUN mkdir -p /app/cache /app/config /app/templates \
    && useradd -m appuser \
    && chown -R appuser:appuser /app

# Utilisation d'un utilisateur non-root
USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 