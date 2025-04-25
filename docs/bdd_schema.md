# MnemoLite – Schéma SQL Raffiné (v1.1.0 / 2025.04.26)

## Contexte
Ce schéma est le résultat d'un brainstorming basé sur le PFD v1.2.1 et le PRD v1.0.1, visant une architecture 100% PostgreSQL optimisée pour un déploiement local. Il combine une table principale `events` partitionnée pour la recherche temporelle/vectorielle et des tables `nodes`/`edges` pour une représentation conceptuelle/événementielle du graphe.

---

## Extensions Requises

```sql
------------------------------------------------------------------
-- Extensions
------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS pgcrypto; -- Pour gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgvector; -- Pour VECTOR et index HNSW
-- CREATE EXTENSION IF NOT EXISTS pg_partman; -- A installer séparément si besoin
```

---

## Schéma SQL

```sql
------------------------------------------------------------------
-- Table Principale: events (partitionnée)
------------------------------------------------------------------
CREATE TABLE events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    content     JSONB NOT NULL,             -- Contenu flexible: { "type": "prompt", "role": "user", "text": "..." } ou { "type": "decision", ... }
    embedding   VECTOR(1536),               -- Embedding de 'content' ou d'une partie pertinente
    metadata    JSONB DEFAULT '{}'::jsonb   -- Tags, source, rule_id, session_id, event_type, memory_type, etc.
)
PARTITION BY RANGE (timestamp);

-- Création de la première partition (exemple, pg_partman s'en chargera ensuite)
CREATE TABLE events_p2025_04 PARTITION OF events
FOR VALUES FROM ('2025-04-01') TO ('2025-05-01');

-- Index GIN sur metadata pour recherches flexibles
CREATE INDEX events_metadata_gin_idx ON events USING GIN (metadata jsonb_path_ops);

-- Index HNSW sur embedding (doit être créé sur chaque partition !)
-- Exemple pour une partition (gestion via pg_partman hooks recommandée):
-- CREATE INDEX ON events_p2025_04 USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

------------------------------------------------------------------
-- Tables Graphe Conceptuel/Événementiel
------------------------------------------------------------------
CREATE TABLE nodes (
    node_id         UUID PRIMARY KEY, -- Généralement un event.id, mais peut être autre chose (concept généré)
    node_type       TEXT NOT NULL,    -- Ex: 'event', 'concept', 'entity', 'rule'
    label           TEXT,             -- Nom lisible pour affichage/requête
    properties      JSONB DEFAULT '{}'::jsonb, -- Attributs additionnels du nœud
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX nodes_type_idx ON nodes(node_type);
-- Optionnel: Index sur label si recherche fréquente par nom
-- CREATE INDEX nodes_label_idx ON nodes USING gin (label gin_trgm_ops);

CREATE TABLE edges (
    edge_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_node_id  UUID NOT NULL, -- Référence nodes.node_id (PAS de FK pour flexibilité si nœud non encore créé)
    target_node_id  UUID NOT NULL, -- Référence nodes.node_id (PAS de FK)
    relation_type   TEXT NOT NULL, -- Ex: 'causes', 'mentions', 'related_to', 'follows', 'uses_tool'
    properties      JSONB DEFAULT '{}'::jsonb, -- Poids, timestamp de la relation, etc.
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX edges_source_idx ON edges(source_node_id);
CREATE INDEX edges_target_idx ON edges(target_node_id);
CREATE INDEX edges_relation_type_idx ON edges(relation_type);
-- Optionnel: Index composite pour requêtes fréquentes
-- CREATE INDEX edges_source_type_target_idx ON edges(source_node_id, relation_type, target_node_id);

-- Note: Pas de contraintes de clé étrangère (FK) sur edges pour permettre de
-- créer des relations même si l'un des nœuds n'existe pas encore (ex: référence future)
-- ou si les node_id ne sont pas tous dans la table nodes (simplification).
-- La cohérence est gérée par l'application ou des checks périodiques.
```

---

## Rationale des Choix Principaux

1.  **Table `events` Cœur :** Stocke chaque interaction atomique avec contexte (`content`, `metadata`) et vecteur (`embedding`). Source de vérité temporelle/sémantique. Partitionnement pour scalabilité temporelle locale.
2.  **Flexibilité JSONB :** `content` et `metadata` en JSONB permettent de stocker divers types d'événements/infos sans altérer le schéma. Index GIN pour recherche efficace.
3.  **Graphe `nodes`/`edges` Conceptuel :** Découplé du texte brut. L'application crée les nœuds (événements, concepts...) et liens pertinents (`causes`, `mentions`...). Cible les requêtes causales simples (≤ 3 sauts) via CTE SQL.
4.  **Indexation Optimisée Localement :** HNSW pour vecteurs (sur partitions), GIN pour métadonnées, B-tree pour graphe.
5.  **Simplicité Locale :** Schéma épuré, pas de tables de lookup superflues, pas de trigger complexe sur `INSERT` (logique dans l'application).

---

**Version :** 1.1.0 (aligné ARCH 1.1.0)
**Date :** 2025-04-26
**Auteur :** Giak