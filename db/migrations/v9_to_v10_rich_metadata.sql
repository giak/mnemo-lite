-- Migration: v9 to v10 - Rich Metadata & Metrics Tables
-- Date: 2025-11-02
-- Description: Add dedicated tables for detailed metadata and computed metrics

BEGIN;

-- Table 1: Detailed metadata (flexible JSONB storage)
CREATE TABLE IF NOT EXISTS detailed_metadata (
    metadata_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id UUID NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    chunk_id UUID NOT NULL REFERENCES code_chunks(id) ON DELETE CASCADE,

    -- Metadata payload (calls, imports, signature, context)
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Version tracking
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(node_id, version)
);

-- Indexes for detailed_metadata
CREATE INDEX idx_detailed_metadata_node ON detailed_metadata(node_id);
CREATE INDEX idx_detailed_metadata_chunk ON detailed_metadata(chunk_id);
CREATE INDEX idx_detailed_metadata_version ON detailed_metadata(version);
CREATE INDEX idx_detailed_metadata_gin ON detailed_metadata USING GIN (metadata);

-- Table 2: Computed metrics (normalized columns for performance)
CREATE TABLE IF NOT EXISTS computed_metrics (
    metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id UUID NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    chunk_id UUID NOT NULL REFERENCES code_chunks(id) ON DELETE CASCADE,
    repository TEXT NOT NULL,

    -- Complexity metrics
    cyclomatic_complexity INTEGER DEFAULT 0,
    cognitive_complexity INTEGER DEFAULT 0,
    lines_of_code INTEGER DEFAULT 0,

    -- Coupling metrics
    afferent_coupling INTEGER DEFAULT 0,  -- Incoming dependencies
    efferent_coupling INTEGER DEFAULT 0,  -- Outgoing dependencies

    -- Graph centrality (calculated)
    pagerank_score FLOAT,
    betweenness_centrality FLOAT,

    -- Version tracking
    version INTEGER DEFAULT 1,
    computed_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(node_id, version)
);

-- Indexes for computed_metrics
CREATE INDEX idx_computed_metrics_node ON computed_metrics(node_id);
CREATE INDEX idx_computed_metrics_chunk ON computed_metrics(chunk_id);
CREATE INDEX idx_computed_metrics_repository ON computed_metrics(repository);
CREATE INDEX idx_computed_metrics_version ON computed_metrics(version);
CREATE INDEX idx_computed_metrics_complexity ON computed_metrics(cyclomatic_complexity DESC);
CREATE INDEX idx_computed_metrics_pagerank ON computed_metrics(pagerank_score DESC NULLS LAST);

-- Table 3: Edge weights (relationship strength)
CREATE TABLE IF NOT EXISTS edge_weights (
    weight_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    edge_id UUID NOT NULL REFERENCES edges(edge_id) ON DELETE CASCADE,

    -- Weight components
    call_count INTEGER DEFAULT 1,  -- Unique calls (not loop-multiplied)
    importance_score FLOAT DEFAULT 1.0,  -- 0-1 based on PageRank propagation
    is_critical_path BOOLEAN DEFAULT FALSE,

    -- Version tracking
    version INTEGER DEFAULT 1,
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(edge_id, version)
);

-- Indexes for edge_weights
CREATE INDEX idx_edge_weights_edge ON edge_weights(edge_id);
CREATE INDEX idx_edge_weights_version ON edge_weights(version);
CREATE INDEX idx_edge_weights_importance ON edge_weights(importance_score DESC);

-- Add columns to existing edges table (optimization)
ALTER TABLE edges
    ADD COLUMN IF NOT EXISTS weight FLOAT DEFAULT 1.0,
    ADD COLUMN IF NOT EXISTS is_external BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_edges_weight ON edges(weight DESC);
CREATE INDEX IF NOT EXISTS idx_edges_external ON edges(is_external);

COMMIT;
