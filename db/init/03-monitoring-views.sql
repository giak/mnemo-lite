-- db/init/03-monitoring-views.sql
-- Vues de monitoring pour décider quand activer le partitionnement

------------------------------------------------------------------
-- Vue: partitioning_readiness
------------------------------------------------------------------
-- Vue qui indique si le partitionnement devrait être activé
-- Utiliser: SELECT * FROM partitioning_readiness;

CREATE OR REPLACE VIEW partitioning_readiness AS
WITH event_stats AS (
    SELECT
        COUNT(*) AS total_events,
        MIN(timestamp) AS oldest_event,
        MAX(timestamp) AS newest_event,
        EXTRACT(EPOCH FROM (MAX(timestamp) - MIN(timestamp))) / 86400 AS age_days,
        pg_size_pretty(pg_total_relation_size('events')) AS table_size,
        pg_total_relation_size('events') AS table_size_bytes
    FROM events
),
thresholds AS (
    SELECT
        500000 AS event_threshold,         -- Seuil recommandé: 500k events
        365 AS age_threshold_days,         -- Ou 1 an de données
        10737418240 AS size_threshold_bytes -- Ou 10 GB (10 * 1024^3)
)
SELECT
    -- Statistiques actuelles
    es.total_events,
    es.oldest_event,
    es.newest_event,
    ROUND(es.age_days::numeric, 1) AS age_days,
    es.table_size,

    -- Seuils
    t.event_threshold,
    t.age_threshold_days,
    pg_size_pretty(t.size_threshold_bytes) AS size_threshold,

    -- Distances aux seuils (combien reste-t-il ?)
    (t.event_threshold - es.total_events) AS events_until_threshold,
    ROUND((t.age_threshold_days - es.age_days)::numeric, 1) AS days_until_threshold,
    pg_size_pretty(t.size_threshold_bytes - es.table_size_bytes) AS size_until_threshold,

    -- Progression (% du seuil atteint)
    ROUND((es.total_events::numeric / t.event_threshold * 100), 1) AS event_progress_pct,
    ROUND((es.age_days / t.age_threshold_days * 100), 1) AS age_progress_pct,
    ROUND((es.table_size_bytes::numeric / t.size_threshold_bytes * 100), 1) AS size_progress_pct,

    -- Recommandation
    CASE
        WHEN es.total_events >= t.event_threshold
          OR es.age_days >= t.age_threshold_days
          OR es.table_size_bytes >= t.size_threshold_bytes
        THEN '🔴 ACTIVER PARTITIONNEMENT MAINTENANT'
        WHEN es.total_events >= t.event_threshold * 0.8
          OR es.age_days >= t.age_threshold_days * 0.8
          OR es.table_size_bytes >= t.size_threshold_bytes * 0.8
        THEN '🟡 PRÉPARER ACTIVATION (80% du seuil)'
        WHEN es.total_events >= t.event_threshold * 0.5
          OR es.age_days >= t.age_threshold_days * 0.5
          OR es.table_size_bytes >= t.size_threshold_bytes * 0.5
        THEN '🟢 SURVEILLER (50% du seuil)'
        ELSE '🟢 OK (< 50% du seuil)'
    END AS recommendation,

    -- Estimation: quand atteindre le seuil ?
    CASE
        WHEN es.total_events < 100 THEN 'Pas assez de données pour estimer'
        WHEN es.age_days < 7 THEN 'Pas assez de données pour estimer'
        ELSE
            pg_size_pretty(
                ROUND(
                    (t.event_threshold - es.total_events) /
                    (es.total_events::numeric / GREATEST(es.age_days, 1)) * 86400
                )::bigint
            ) || ' jours restants (estimation)'
    END AS estimated_days_until_threshold

FROM event_stats es
CROSS JOIN thresholds t;

COMMENT ON VIEW partitioning_readiness IS
'Vue de monitoring pour décider quand activer le partitionnement.
Vérifie 3 seuils: nombre d''events (500k), âge des données (1 an), taille table (10 GB).
Activation recommandée quand UN des seuils est atteint.';

------------------------------------------------------------------
-- Vue: partition_performance_preview
------------------------------------------------------------------
-- Simule les performances avec partitionnement mensuel

CREATE OR REPLACE VIEW partition_performance_preview AS
WITH monthly_distribution AS (
    SELECT
        DATE_TRUNC('month', timestamp) AS month,
        COUNT(*) AS events_per_partition,
        pg_size_pretty(
            COUNT(*) * (
                pg_column_size(ROW(id, timestamp, content, embedding, metadata))
            )
        ) AS estimated_partition_size,
        MIN(timestamp) AS partition_start,
        MAX(timestamp) AS partition_end
    FROM events
    GROUP BY DATE_TRUNC('month', timestamp)
    ORDER BY month DESC
)
SELECT
    month,
    events_per_partition,
    estimated_partition_size,
    partition_start,
    partition_end,
    ROUND(
        events_per_partition::numeric /
        SUM(events_per_partition) OVER () * 100,
        2
    ) AS pct_of_total,
    -- Qualité de la partition (idéalement 50k-200k events/partition)
    CASE
        WHEN events_per_partition < 10000 THEN '⚠️  Trop petite'
        WHEN events_per_partition > 500000 THEN '⚠️  Trop grande'
        WHEN events_per_partition BETWEEN 50000 AND 200000 THEN '✅ Optimale'
        ELSE '🟡 Acceptable'
    END AS partition_quality
FROM monthly_distribution;

COMMENT ON VIEW partition_performance_preview IS
'Simule comment les données seraient distribuées avec partitionnement mensuel.
Aide à vérifier si la granularité mensuelle est adaptée au volume de données.';

------------------------------------------------------------------
-- Vue: index_maintenance_preview
------------------------------------------------------------------
-- Estime le temps de création d'indexes HNSW sur partitions

CREATE OR REPLACE VIEW index_maintenance_preview AS
WITH event_counts AS (
    SELECT COUNT(*) AS total_events FROM events
),
partition_estimate AS (
    SELECT
        CEIL(
            EXTRACT(EPOCH FROM (MAX(timestamp) - MIN(timestamp))) / (30 * 86400)
        ) AS estimated_partitions
    FROM events
)
SELECT
    ec.total_events,
    pe.estimated_partitions,
    ROUND(ec.total_events::numeric / GREATEST(pe.estimated_partitions, 1)) AS avg_events_per_partition,

    -- Estimation temps de création index HNSW (environ 500 events/sec)
    pg_size_pretty(
        ROUND(
            (ec.total_events::numeric / GREATEST(pe.estimated_partitions, 1)) / 500
        )::bigint
    ) || ' secondes par partition' AS estimated_index_creation_time,

    pg_size_pretty(
        ROUND(pe.estimated_partitions * (ec.total_events::numeric / GREATEST(pe.estimated_partitions, 1)) / 500)::bigint
    ) || ' secondes au total' AS total_index_creation_time,

    -- Recommandation
    CASE
        WHEN pe.estimated_partitions < 6 THEN '✅ Peu de partitions, maintenance facile'
        WHEN pe.estimated_partitions BETWEEN 6 AND 24 THEN '🟡 Maintenance modérée'
        WHEN pe.estimated_partitions > 24 THEN '🔴 Beaucoup de partitions, considérer intervalles trimestriels'
        ELSE '❓ Pas assez de données'
    END AS maintenance_recommendation

FROM event_counts ec
CROSS JOIN partition_estimate pe;

COMMENT ON VIEW index_maintenance_preview IS
'Estime l''effort de maintenance des indexes HNSW après activation du partitionnement.
Aide à anticiper le temps nécessaire pour la création initiale des indexes.';
