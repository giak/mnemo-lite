-- Fonctions vectorielles pour l'API

-- Recherche sémantique
CREATE OR REPLACE FUNCTION search_memories(
  query_embedding VECTOR(1536),
  limit_results INTEGER DEFAULT 10,
  memory_type_filter TEXT DEFAULT NULL,
  event_type_filter TEXT DEFAULT NULL,
  role_filter INTEGER DEFAULT NULL,
  start_date TIMESTAMPTZ DEFAULT NULL,
  end_date TIMESTAMPTZ DEFAULT NULL
) RETURNS TABLE (
  id UUID,
  timestamp TIMESTAMPTZ,
  memory_type TEXT,
  event_type TEXT,
  role_id INTEGER,
  content JSONB,
  similarity FLOAT,
  metadata JSONB
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    e.id,
    e.timestamp,
    e.memory_type,
    e.event_type,
    e.role_id,
    e.content,
    1 - (e.embedding <=> query_embedding) AS similarity,
    e.metadata
  FROM 
    events e
  WHERE 
    e.embedding IS NOT NULL
    AND (memory_type_filter IS NULL OR e.memory_type = memory_type_filter)
    AND (event_type_filter IS NULL OR e.event_type = event_type_filter)
    AND (role_filter IS NULL OR e.role_id = role_filter)
    AND (start_date IS NULL OR e.timestamp >= start_date)
    AND (end_date IS NULL OR e.timestamp <= end_date)
    AND (e.expiration IS NULL OR e.expiration > NOW())
  ORDER BY 
    e.embedding <=> query_embedding
  LIMIT limit_results;
END;
$$ LANGUAGE plpgsql;

-- Récupérer des événements liés
CREATE OR REPLACE FUNCTION get_related_events(
  event_id UUID,
  relation_type TEXT DEFAULT NULL,
  limit_results INTEGER DEFAULT 10
) RETURNS TABLE (
  id UUID,
  source_id UUID,
  target_id UUID,
  relation_type TEXT,
  target_timestamp TIMESTAMPTZ,
  target_memory_type TEXT,
  target_event_type TEXT,
  target_role_id INTEGER,
  target_content JSONB
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    r.id,
    r.source_id,
    r.target_id,
    r.relation_type,
    e.timestamp,
    e.memory_type,
    e.event_type,
    e.role_id,
    e.content
  FROM 
    relations r
    JOIN events e ON r.target_id = e.id
  WHERE 
    r.source_id = event_id
    AND (relation_type IS NULL OR r.relation_type = relation_type)
  ORDER BY 
    e.timestamp DESC
  LIMIT limit_results;
END;
$$ LANGUAGE plpgsql;

-- Fonction pour supprimer la mémoire associée à une session
CREATE OR REPLACE FUNCTION forget_session(session_id TEXT) RETURNS INTEGER AS $$
DECLARE
  affected_rows INTEGER;
BEGIN
  -- Suppression de toutes les relations associées
  DELETE FROM relations
  WHERE source_id IN (SELECT id FROM events WHERE metadata->>'session_id' = session_id)
     OR target_id IN (SELECT id FROM events WHERE metadata->>'session_id' = session_id);
  
  -- Archivage des événements
  INSERT INTO events_archive
  SELECT *, NOW() 
  FROM events 
  WHERE metadata->>'session_id' = session_id;
  
  -- Suppression des événements
  DELETE FROM events
  WHERE metadata->>'session_id' = session_id;
  
  GET DIAGNOSTICS affected_rows = ROW_COUNT;
  RETURN affected_rows;
END;
$$ LANGUAGE plpgsql;

-- Création de la vue des sessions actives récentes
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
  AND timestamp > NOW() - INTERVAL '7 days'
GROUP BY 
  metadata->>'session_id'
ORDER BY 
  MAX(timestamp) DESC;

-- Fonction pour résumer une session
CREATE OR REPLACE FUNCTION summarize_session(
  p_session_id TEXT,
  p_limit INTEGER DEFAULT 100
) RETURNS TABLE (
  session_id TEXT,
  started_at TIMESTAMPTZ,
  last_activity TIMESTAMPTZ, 
  event_count BIGINT,
  recent_events JSONB
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
        jsonb_build_object(
          'id', id,
          'timestamp', timestamp,
          'event_type', event_type,
          'role_id', role_id,
          'content', content
        ) ORDER BY timestamp DESC
      ) AS events
    FROM (
      SELECT id, timestamp, event_type, role_id, content
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
    session_meta sm,
    recent_evts re;
END;
$$ LANGUAGE plpgsql;

-- Tâche planifiée pour le nettoyage des données expirées
SELECT cron.schedule(
  'clean-expired-data',
  '0 4 * * *',  -- tous les jours à 4h00
  $$
    -- Archiver les données expirées
    INSERT INTO events_archive
    SELECT *, NOW() 
    FROM events 
    WHERE expiration < NOW();
    
    -- Supprimer les données expirées
    DELETE FROM events 
    WHERE expiration < NOW();
    
    -- Rafraîchir la vue matérialisée
    REFRESH MATERIALIZED VIEW active_memories;
  $$
);

-- Tâche pour le nettoyage des données de plus de 90 jours dans l'outbox
SELECT cron.schedule(
  'clean-outbox',
  '0 5 * * *',  -- tous les jours à 5h00
  $$
    DELETE FROM chroma_outbox 
    WHERE created_at < NOW() - INTERVAL '90 days';
  $$
); 