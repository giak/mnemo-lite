# Use the official pgvector image as the base (PostgreSQL 18 + pgvector 0.8.1)
FROM pgvector/pgvector:pg18

# Install pg_partman
# Need root privileges to install packages
USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-18-partman \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Switch back to the default postgres user
USER postgres

# Le reste (CMD, ENTRYPOINT, etc.) est hérité de l'image de base 