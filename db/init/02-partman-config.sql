-- db/init/02-partman-config.sql
-- Configuration pg_partman pour la table events (DÉSACTIVÉE)

------------------------------------------------------------------
-- PARTITIONNEMENT POSTPONÉ (Phase 3 - Option A)
------------------------------------------------------------------
-- Date: 2025-10-12
-- Décision: Postponer le partitionnement jusqu'à ~500k events
--
-- RATIONALE:
-- - Table events actuellement NON partitionnée (voir 01-init.sql ligne 40)
-- - Partitionnement bénéfique uniquement à partir de ~500k events
-- - Overhead actuel: +2-3ms latence, complexité opérationnelle inutile
-- - Tipping point: ~500k events où partition pruning compense l'overhead
--
-- MONITORING:
-- - Vue partitioning_readiness (voir 03-monitoring-views.sql)
-- - Vérifier régulièrement: SELECT * FROM partitioning_readiness;
--
-- ACTIVATION FUTURE:
-- - Script prêt: db/scripts/enable_partitioning.sql
-- - Downtime requis: ~30min pour migration
-- - Déclencher quand: event_count > 500000
------------------------------------------------------------------

-- Configuration pg_partman DÉSACTIVÉE pour le moment
-- Le code ci-dessous sera décommenté lors de l'activation future

/*
-- Create the partitioning configuration and initial partitions for public.events
-- This function handles inserting into partman.part_config and creating partitions.
SELECT partman.create_parent(
    p_parent_table := 'public.events',       -- Parent table name (schema-qualified)
    p_control := 'timestamp',                -- Control column (partitioning key)
    p_type := 'range',                       -- Partitioning strategy (range for time)
    p_interval := '1 month',                 -- Partition interval (correct syntax)
    p_premake := 4,                          -- Create 4 future partitions ahead of time
    p_start_partition := (now() - interval '1 month')::text -- Optional: Start partitioning from last month
);

-- Note: Periodic maintenance needs to be scheduled separately (e.g., via pg_cron)
-- using partman.run_maintenance_proc() or similar.
*/

-- Pour activer le partitionnement plus tard:
-- 1. Exécuter: db/scripts/enable_partitioning.sql
-- 2. Décommenter le code ci-dessus
-- 3. Redémarrer les services: make restart
