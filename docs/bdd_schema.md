# MnemoLite – Schéma SQL enrichi (v2024.04)

## Tables principales

### `events`
```sql
CREATE TABLE events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  timestamp TIMESTAMPTZ NOT NULL,
  expiration TIMESTAMPTZ, -- pour TTL automatique
  memory_type TEXT REFERENCES memory_types(code),
  event_type TEXT REFERENCES event_types(code),
  role_id INTEGER REFERENCES roles(id),
  content JSONB NOT NULL,
  embedding VECTOR(1536),
  metadata JSONB DEFAULT '{}'
);
CREATE INDEX ON events(timestamp);
CREATE INDEX ON events USING hnsw(embedding);
```

### `roles`
```sql
CREATE TABLE roles (
  id SERIAL PRIMARY KEY,
  role_name TEXT UNIQUE NOT NULL
);
```

### `memory_types`
```sql
CREATE TABLE memory_types (
  code TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  description TEXT
);
```

### `event_types`
```sql
CREATE TABLE event_types (
  code TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  description TEXT
);
```

### `relations`
```sql
CREATE TABLE relations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id UUID REFERENCES events(id),
  target_id UUID REFERENCES events(id),
  relation_type TEXT CHECK (relation_type IN ('causes', 'depends_on', 'relates_to')),
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ON relations(source_id);
CREATE INDEX ON relations(target_id);
```

## Tables temporelles

### `sequences` & `sequence_events`
```sql
CREATE TABLE sequences (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  description TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE sequence_events (
  sequence_id UUID REFERENCES sequences(id),
  event_id UUID REFERENCES events(id),
  position INTEGER NOT NULL,
  PRIMARY KEY (sequence_id, event_id)
);
```

### `events_archive`
```sql
CREATE TABLE events_archive (
  LIKE events INCLUDING ALL,
  archived_at TIMESTAMPTZ DEFAULT NOW()
);
```

## Vues et indexation

### Vue matérialisée (optionnelle)
```sql
CREATE MATERIALIZED VIEW active_memories AS
SELECT * FROM events WHERE expiration IS NULL OR expiration > NOW();
```

### Partitionnement mensuel (optionnel)
```sql
-- via pg_partman ou manuellement
CREATE TABLE events_2024_04 PARTITION OF events
FOR VALUES FROM ('2024-04-01') TO ('2024-05-01');
```

---

## Index complémentaires recommandés
```sql
CREATE INDEX ON events ((metadata->>'rule_id'));
CREATE INDEX ON events ((metadata->>'session_id'));
CREATE INDEX ON events ((metadata->>'source_file'));
```

## À venir : Graphe avec pgGraph/pgRouting + tables d'adjacence
Graphes avec tables edges(src,dst,props) + vues. 0 dépendance externe, réutilise SQL, fenêtre analytique.

---

**Version : 2024.04.24  
Auteur : Giak**