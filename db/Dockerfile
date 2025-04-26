# Use the official pgvector image as the base
FROM pgvector/pgvector:pg17

# Install pg_partman
# Need root privileges to install packages
USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-17-partman \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Switch back to the default postgres user
USER postgres

# Le reste (CMD, ENTRYPOINT, etc.) est hérité de l'image de base 