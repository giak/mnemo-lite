# Utiliser l'image officielle pgvector comme base
FROM pgvector/pgvector:pg17

# Mettre à jour les paquets et installer pg_partman
# pg_partman dépend de postgresql-17, qui est déjà dans l'image de base.
# Il faut s'assurer que les dépôts PGDG sont bien actifs (normalement le cas ici).
USER root
RUN apt-get update && \
    apt-get install -y --no-install-recommends postgresql-17-partman && \
    # Nettoyage
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Revenir à l'utilisateur par défaut de l'image postgres (habituellement 'postgres')
USER postgres

# Le reste (CMD, ENTRYPOINT, etc.) est hérité de l'image de base 