-- Migration: Persist graph views in Postgres (network selections, etc.)
-- Date: 2026-06-05

CREATE TABLE IF NOT EXISTS graph_views (
    id VARCHAR(255) PRIMARY KEY,
    workspace_id VARCHAR(255) NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    view_type VARCHAR(100) NOT NULL DEFAULT 'network',
    kind VARCHAR(50) NOT NULL DEFAULT 'network',
    visibility VARCHAR(20) NOT NULL DEFAULT 'workspace',
    creator_id VARCHAR(255) REFERENCES users(id) ON DELETE SET NULL,
    graph_id VARCHAR(255) NOT NULL,
    graph_uri TEXT NOT NULL,
    state TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_graph_views_workspace ON graph_views(workspace_id);
CREATE INDEX IF NOT EXISTS idx_graph_views_workspace_visibility ON graph_views(workspace_id, visibility);
CREATE INDEX IF NOT EXISTS idx_graph_views_creator ON graph_views(creator_id);
