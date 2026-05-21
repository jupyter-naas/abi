-- Migration: Per-workspace enable state for named graphs
-- Date: 2026-05-21

CREATE TABLE IF NOT EXISTS graph_configs (
    id VARCHAR(255) PRIMARY KEY,
    workspace_id VARCHAR(255) NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    graph_uri VARCHAR(1024) NOT NULL,
    name VARCHAR(255) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_graph_configs_workspace_graph_uri UNIQUE (workspace_id, graph_uri)
);

CREATE INDEX IF NOT EXISTS idx_graph_configs_workspace ON graph_configs(workspace_id);
CREATE INDEX IF NOT EXISTS idx_graph_configs_graph_uri ON graph_configs(graph_uri);
