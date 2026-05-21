-- Migration: Per-workspace enable state for ontology files
-- Date: 2026-05-21

CREATE TABLE IF NOT EXISTS ontology_configs (
    id VARCHAR(255) PRIMARY KEY,
    workspace_id VARCHAR(255) NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    path VARCHAR(1024) NOT NULL,
    name VARCHAR(255) NOT NULL,
    module_name VARCHAR(255) NOT NULL,
    submodule_name VARCHAR(255),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_ontology_configs_workspace_path UNIQUE (workspace_id, path)
);

CREATE INDEX IF NOT EXISTS idx_ontology_configs_workspace ON ontology_configs(workspace_id);
CREATE INDEX IF NOT EXISTS idx_ontology_configs_path ON ontology_configs(path);
