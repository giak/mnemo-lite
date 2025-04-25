-- Fonctions et Vues Utilitaires pour MnemoLite (v1.1.0)
-- Alignées sur le schéma bdd_schema.md v1.1.0

-- Recherche sémantique dans les événements
CREATE OR REPLACE FUNCTION search_memories(
  query_embedding VECTOR(1536),
  limit_results INTEGER DEFAULT 10,
  metadata_filter JSONB DEFAULT NULL, -- Filtre JSONB, ex: '{"memory_type": "episodic", "role": "user"}'
  start_date TIMESTAMPTZ DEFAULT NULL,
  end_date TIMESTAMPTZ DEFAULT NULL
) RETURNS TABLE (
  id UUID,
  timestamp TIMESTAMPTZ,
  content JSONB,
  similarity FLOAT,
  metadata JSONB
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    e.id,
    e.timestamp,
    e.content,
    1 - (e.embedding <=> query_embedding) AS similarity, -- Cosine similarity
    e.metadata
  FROM 
    events e
  WHERE 
    e.embedding IS NOT NULL
    AND (start_date IS NULL OR e.timestamp >= start_date)
    AND (end_date IS NULL OR e.timestamp <= end_date)
    -- Le filtre JSONB permet de chercher sur n'importe quelle clé/valeur dans metadata
    AND (metadata_filter IS NULL OR e.metadata @> metadata_filter)
    -- NOTE: Expiration non gérée ici, supposée gérée par pg_partman ou requêtes spécifiques
  ORDER BY 
    e.embedding <=> query_embedding -- Ordre par similarité cosinus (plus proche de 1 est mieux)
  LIMIT limit_results;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION search_memories IS 'Recherche des événements par similarité sémantique (cosinus) avec filtres optionnels sur dates et métadonnées JSONB.';

-- Fonction pour supprimer la mémoire associée à une session
-- ATTENTION: Ne supprime que les événements. Les nœuds/arêtes associés dans le graphe ne sont pas touchés.
CREATE OR REPLACE FUNCTION forget_session(p_session_id TEXT) RETURNS BIGINT AS $$
DECLARE
  deleted_count BIGINT;
BEGIN
  -- Suppression des événements correspondants
  WITH deleted AS (
    DELETE FROM events
    WHERE metadata->>'session_id' = p_session_id
    RETURNING *
  )
  SELECT count(*) INTO deleted_count FROM deleted;
  
  -- Note: Pas d'archivage ici, la rétention est gérée par pg_partman.
  -- Note: Pas de suppression de relations ici, la table relations/edges est gérée séparément.
  
  RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION forget_session IS 'Supprime tous les événements associés à un session_id spécifique dans la table events. Retourne le nombre d'événements supprimés.';

-- Vue des sessions actives récentes (Basée sur metadata->>'session_id')
CREATE OR REPLACE VIEW recent_sessions AS
SELECT 
  metadata->>'session_id' AS session_id,
  MIN(timestamp) AS started_at,
  MAX(timestamp) AS last_activity,
  COUNT(*) AS event_count
FROM 
  events
WHERE 
  metadata->>'session_id' IS NOT NULL
  -- Optionnel: Ajouter un filtre de temps si nécessaire, ex:
  -- AND timestamp > NOW() - INTERVAL '7 days'
GROUP BY 
  metadata->>'session_id'
ORDER BY 
  last_activity DESC;

COMMENT ON VIEW recent_sessions IS 'Vue agrégée montrant les sessions récentes basées sur la présence de session_id dans metadata des événements.';

-- Fonction pour résumer une session (Récupère métadonnées et événements récents)
CREATE OR REPLACE FUNCTION summarize_session(
  p_session_id TEXT,
  p_limit INTEGER DEFAULT 100
) RETURNS TABLE (
  session_id TEXT,
  started_at TIMESTAMPTZ,
  last_activity TIMESTAMPTZ, 
  event_count BIGINT,
  recent_events JSONB -- Liste des événements récents
) AS $$
BEGIN
  RETURN QUERY
  WITH session_meta AS (
    SELECT 
      metadata->>'session_id' AS sid,
      MIN(timestamp) AS started,
      MAX(timestamp) AS last_act,
      COUNT(*) AS cnt
    FROM events
    WHERE metadata->>'session_id' = p_session_id
    GROUP BY metadata->>'session_id'
  ),
  recent_evts AS (
    SELECT 
      jsonb_agg(
        -- Sélection des champs pertinents de l'événement
        jsonb_strip_nulls(jsonb_build_object(
          'id', id,
          'timestamp', timestamp,
          'content', content, -- Inclure le contenu
          'metadata', metadata -- Inclure les métadonnées
        )) ORDER BY timestamp DESC
      ) AS events
    FROM (
      SELECT id, timestamp, content, metadata
      FROM events
      WHERE metadata->>'session_id' = p_session_id
      ORDER BY timestamp DESC
      LIMIT p_limit
    ) e
  )
  SELECT 
    sm.sid AS session_id,
    sm.started AS started_at,
    sm.last_act AS last_activity,
    sm.cnt AS event_count,
    re.events AS recent_events
  FROM 
    session_meta sm
    CROSS JOIN recent_evts re; -- Utiliser CROSS JOIN car recent_evts retourne toujours une ligne (potentiellement avec null ou [] si aucun événement)
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION summarize_session IS 'Fournit un résumé d'une session: métadonnées agrégées et les N événements les plus récents.';

-- NOTE: Les fonctions et triggers liés à la table 'relations' et 'chroma_outbox' ont été supprimés.
-- NOTE: Les tâches cron pour le nettoyage via 'expiration' ou 'chroma_outbox' ont été supprimées.
-- La gestion de la rétention est assurée par pg_partman (configuration manuelle requise).

-- Fin du script setup.sql nettoyé 