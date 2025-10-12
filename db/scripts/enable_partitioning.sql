-- db/scripts/enable_partitioning.sql
-- Script de migration pour activer le partitionnement sur la table events
-- Version: 1.0.0
-- Date: 2025-10-12

------------------------------------------------------------------
-- IMPORTANT: LIRE AVANT EXÉCUTION
------------------------------------------------------------------
-- ⚠️  Ce script nécessite un DOWNTIME de ~30 minutes
-- ⚠️  Faire un BACKUP complet avant exécution
-- ⚠️  Exécuter sur une fenêtre de maintenance planifiée
-- ⚠️  Vérifier que tous les prérequis sont remplis

-- PRÉREQUIS:
-- 1. Backup complet: pg_dump -Fc mnemolite > backup_before_partition.dump
-- 2. Espace disque: 2x la taille de la table events
-- 3. Extension pg_partman installée et configurée
-- 4. Arrêter l'API: docker-compose stop api worker

-- VÉRIFICATIONS PRE-MIGRATION:
-- 1. Volume d'events:       SELECT COUNT(*) FROM events; -- doit être > 500k
-- 2. Espace disque:         SELECT pg_size_pretty(pg_total_relation_size('events'));
-- 3. pg_partman disponible: SELECT partman.check_default();
-- 4. Services arrêtés:      docker ps | grep mnemo-api (doit être vide)

-- DURÉE ESTIMÉE:
-- - 100k events:  ~5 minutes
-- - 500k events:  ~15 minutes
-- - 1M events:    ~30 minutes
-- - 5M events:    ~90 minutes

------------------------------------------------------------------
-- ÉTAPE 1: Vérifications et préparation
------------------------------------------------------------------

\set ON_ERROR_STOP on
\timing on

-- Vérifier que nous sommes bien sur la base mnemolite
DO $$
BEGIN
    IF current_database() != 'mnemolite' THEN
        RAISE EXCEPTION 'Erreur: Ce script doit être exécuté sur la base mnemolite, pas sur %', current_database();
    END IF;
END $$;

-- Enregistrer l'état avant migration
CREATE TABLE IF NOT EXISTS migration_log (
    migration_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    migration_name TEXT NOT NULL,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status TEXT DEFAULT 'in_progress',
    metadata JSONB DEFAULT '{}'
);

INSERT INTO migration_log (migration_name, metadata)
VALUES (
    'enable_partitioning',
    jsonb_build_object(
        'events_count', (SELECT COUNT(*) FROM events),
        'table_size', pg_total_relation_size('events'),
        'oldest_event', (SELECT MIN(timestamp) FROM events),
        'newest_event', (SELECT MAX(timestamp) FROM events)
    )
)
RETURNING *;

-- Afficher statistiques actuelles
\echo '==================== ÉTAT ACTUEL ===================='
SELECT
    COUNT(*) AS total_events,
    MIN(timestamp) AS oldest_event,
    MAX(timestamp) AS newest_event,
    pg_size_pretty(pg_total_relation_size('events')) AS table_size
FROM events;

\echo ''
\echo '==================== PRÊT ? ===================='
\echo 'Appuyez sur Ctrl+C pour annuler, ou Entrée pour continuer...'
\prompt 'Continuer la migration? [yes/no]: ' confirm

DO $$
BEGIN
    IF :'confirm' != 'yes' THEN
        RAISE EXCEPTION 'Migration annulée par l''utilisateur';
    END IF;
END $$;

------------------------------------------------------------------
-- ÉTAPE 2: Renommer la table existante
------------------------------------------------------------------

\echo ''
\echo '==================== ÉTAPE 2: Renommage table ===================='

-- Renommer events → events_old (temporaire)
ALTER TABLE events RENAME TO events_old;

-- Renommer indexes pour éviter conflits
ALTER INDEX IF EXISTS events_timestamp_idx RENAME TO events_old_timestamp_idx;
ALTER INDEX IF EXISTS events_metadata_gin_idx RENAME TO events_old_metadata_gin_idx;
ALTER INDEX IF EXISTS events_embedding_hnsw_idx RENAME TO events_old_embedding_hnsw_idx;

\echo '✓ Table renommée: events → events_old'

------------------------------------------------------------------
-- ÉTAPE 3: Créer la nouvelle table partitionnée
------------------------------------------------------------------

\echo ''
\echo '==================== ÉTAPE 3: Création table partitionnée ===================='

CREATE TABLE events (
    id          UUID NOT NULL DEFAULT gen_random_uuid(),
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    content     JSONB NOT NULL,
    embedding   VECTOR(768),
    metadata    JSONB DEFAULT '{}'::jsonb,
    PRIMARY KEY (id, timestamp)  -- Clé composite requise pour partitionnement
) PARTITION BY RANGE (timestamp);

COMMENT ON TABLE events IS 'Table principale stockant tous les événements atomiques (PARTITIONNÉE par mois).';

\echo '✓ Table partitionnée créée'

------------------------------------------------------------------
-- ÉTAPE 4: Configurer pg_partman
------------------------------------------------------------------

\echo ''
\echo '==================== ÉTAPE 4: Configuration pg_partman ===================='

-- Déterminer la date de début (plus ancien événement)
DO $$
DECLARE
    oldest_timestamp TIMESTAMPTZ;
BEGIN
    SELECT MIN(timestamp) INTO oldest_timestamp FROM events_old;

    -- Créer la configuration partman
    PERFORM partman.create_parent(
        p_parent_table := 'public.events',
        p_control := 'timestamp',
        p_type := 'range',
        p_interval := '1 month',
        p_premake := 4,  -- 4 mois futurs
        p_start_partition := DATE_TRUNC('month', oldest_timestamp)::text
    );

    RAISE NOTICE 'pg_partman configuré avec start_partition: %', DATE_TRUNC('month', oldest_timestamp);
END $$;

\echo '✓ pg_partman configuré'

------------------------------------------------------------------
-- ÉTAPE 5: Créer les partitions nécessaires
------------------------------------------------------------------

\echo ''
\echo '==================== ÉTAPE 5: Création partitions ===================='

-- Laisser pg_partman créer les partitions nécessaires
SELECT partman.run_maintenance('public.events');

-- Afficher les partitions créées
SELECT
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE tablename LIKE 'events_p%'
ORDER BY tablename;

\echo '✓ Partitions créées'

------------------------------------------------------------------
-- ÉTAPE 6: Migrer les données (PHASE LONGUE)
------------------------------------------------------------------

\echo ''
\echo '==================== ÉTAPE 6: Migration données ===================='
\echo '⏳ Cette étape peut prendre plusieurs minutes...'

-- Désactiver les triggers temporairement pour performance
ALTER TABLE events DISABLE TRIGGER ALL;

-- Migrer par lots de 50k pour éviter lock trop long
DO $$
DECLARE
    batch_size INT := 50000;
    total_migrated BIGINT := 0;
    batch_count INT := 0;
    start_time TIMESTAMPTZ;
    estimated_total BIGINT;
BEGIN
    SELECT COUNT(*) INTO estimated_total FROM events_old;
    start_time := clock_timestamp();

    RAISE NOTICE 'Début migration de % événements...', estimated_total;

    LOOP
        -- Migrer un lot
        WITH batch AS (
            SELECT * FROM events_old
            ORDER BY timestamp
            LIMIT batch_size
            OFFSET total_migrated
        )
        INSERT INTO events
        SELECT * FROM batch;

        -- Compter combien ont été migrés
        IF NOT FOUND THEN
            EXIT;
        END IF;

        GET DIAGNOSTICS total_migrated = ROW_COUNT;
        batch_count := batch_count + 1;

        -- Afficher progression tous les 5 lots
        IF batch_count % 5 = 0 THEN
            RAISE NOTICE 'Migré: % événements (%.1f%%) - Temps écoulé: %',
                total_migrated,
                (total_migrated::numeric / estimated_total * 100),
                clock_timestamp() - start_time;
        END IF;

        -- Commit implicite entre chaque lot
        COMMIT;

        EXIT WHEN total_migrated >= estimated_total;
    END LOOP;

    RAISE NOTICE '✓ Migration terminée: % événements en %',
        total_migrated,
        clock_timestamp() - start_time;
END $$;

-- Réactiver les triggers
ALTER TABLE events ENABLE TRIGGER ALL;

-- Vérifier la migration
DO $$
DECLARE
    old_count BIGINT;
    new_count BIGINT;
BEGIN
    SELECT COUNT(*) INTO old_count FROM events_old;
    SELECT COUNT(*) INTO new_count FROM events;

    IF old_count != new_count THEN
        RAISE EXCEPTION 'ERREUR MIGRATION: events_old=% vs events=% ❌', old_count, new_count;
    ELSE
        RAISE NOTICE '✓ Vérification OK: % événements migrés', new_count;
    END IF;
END $$;

------------------------------------------------------------------
-- ÉTAPE 7: Créer les indexes (PHASE LONGUE)
------------------------------------------------------------------

\echo ''
\echo '==================== ÉTAPE 7: Création indexes ===================='
\echo '⏳ Cette étape peut prendre plusieurs minutes...'

-- Indexes hérités automatiquement sur chaque partition
CREATE INDEX events_timestamp_idx ON events (timestamp);
CREATE INDEX events_metadata_gin_idx ON events USING GIN (metadata jsonb_path_ops);

\echo '✓ Indexes B-tree et GIN créés (hérités par partitions)'

-- Créer index HNSW sur CHAQUE partition individuellement
\echo ''
\echo 'Création indexes HNSW sur chaque partition...'

DO $$
DECLARE
    partition_name TEXT;
    start_time TIMESTAMPTZ;
BEGIN
    FOR partition_name IN
        SELECT tablename
        FROM pg_tables
        WHERE tablename LIKE 'events_p%'
        ORDER BY tablename
    LOOP
        start_time := clock_timestamp();
        RAISE NOTICE 'Création index HNSW sur %...', partition_name;

        -- Créer index HNSW (seulement si partition non vide)
        EXECUTE format(
            'CREATE INDEX %I ON %I USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)',
            partition_name || '_embedding_hnsw_idx',
            partition_name
        );

        RAISE NOTICE '✓ Index HNSW créé sur % en %', partition_name, clock_timestamp() - start_time;
    END LOOP;
END $$;

\echo '✓ Tous les indexes HNSW créés'

------------------------------------------------------------------
-- ÉTAPE 8: Nettoyer l'ancienne table
------------------------------------------------------------------

\echo ''
\echo '==================== ÉTAPE 8: Nettoyage ===================='

-- NE PAS supprimer events_old immédiatement !
-- La garder pendant quelques jours pour vérification

-- Créer une vue de validation
CREATE OR REPLACE VIEW migration_validation AS
SELECT
    'events_old' AS table_name,
    COUNT(*) AS row_count,
    MIN(timestamp) AS oldest,
    MAX(timestamp) AS newest,
    pg_size_pretty(pg_total_relation_size('events_old')) AS size
FROM events_old
UNION ALL
SELECT
    'events' AS table_name,
    COUNT(*) AS row_count,
    MIN(timestamp) AS oldest,
    MAX(timestamp) AS newest,
    pg_size_pretty(pg_total_relation_size('events')) AS size
FROM events;

SELECT * FROM migration_validation;

\echo ''
\echo '⚠️  IMPORTANT:'
\echo 'La table events_old a été conservée pour vérification.'
\echo 'Après validation (quelques jours), la supprimer avec:'
\echo '    DROP TABLE events_old CASCADE;'
\echo ''

------------------------------------------------------------------
-- ÉTAPE 9: Configurer la maintenance automatique
------------------------------------------------------------------

\echo ''
\echo '==================== ÉTAPE 9: Configuration maintenance ===================='

-- Configurer la rétention (12 mois)
UPDATE partman.part_config
SET
    retention = '12 months',
    retention_keep_table = FALSE,  -- Supprimer vraiment les vieilles partitions
    infinite_time_partitions = TRUE
WHERE parent_table = 'public.events';

-- Activer la maintenance automatique (nécessite pg_cron)
-- Si pg_cron n'est pas disponible, ajouter dans crontab système:
--   0 3 * * * psql -U mnemo -d mnemolite -c "SELECT partman.run_maintenance('public.events');"

\echo '✓ Configuration maintenance terminée'

------------------------------------------------------------------
-- ÉTAPE 10: Marquer la migration comme terminée
------------------------------------------------------------------

UPDATE migration_log
SET
    completed_at = NOW(),
    status = 'completed',
    metadata = metadata || jsonb_build_object(
        'partitions_created', (SELECT COUNT(*) FROM pg_tables WHERE tablename LIKE 'events_p%'),
        'final_events_count', (SELECT COUNT(*) FROM events),
        'migration_duration', EXTRACT(EPOCH FROM (NOW() - started_at))
    )
WHERE migration_name = 'enable_partitioning'
  AND status = 'in_progress';

------------------------------------------------------------------
-- RÉSUMÉ FINAL
------------------------------------------------------------------

\echo ''
\echo '==================== ✅ MIGRATION TERMINÉE ===================='
\echo ''

SELECT
    'Total events' AS metric,
    COUNT(*)::text AS value
FROM events
UNION ALL
SELECT
    'Partitions créées',
    COUNT(*)::text
FROM pg_tables
WHERE tablename LIKE 'events_p%'
UNION ALL
SELECT
    'Taille totale',
    pg_size_pretty(pg_total_relation_size('events'))
FROM (SELECT 1) x
UNION ALL
SELECT
    'Durée migration',
    metadata->>'migration_duration' || ' secondes'
FROM migration_log
WHERE migration_name = 'enable_partitioning'
  AND status = 'completed'
ORDER BY metric;

\echo ''
\echo '🎉 Partitionnement activé avec succès!'
\echo ''
\echo 'PROCHAINES ÉTAPES:'
\echo '1. Décommenter le code dans db/init/02-partman-config.sql'
\echo '2. Redémarrer les services: docker-compose up -d'
\echo '3. Vérifier logs API: docker-compose logs -f api'
\echo '4. Tester requêtes: SELECT * FROM partitioning_readiness;'
\echo '5. Après validation (3-7 jours): DROP TABLE events_old CASCADE;'
\echo ''
