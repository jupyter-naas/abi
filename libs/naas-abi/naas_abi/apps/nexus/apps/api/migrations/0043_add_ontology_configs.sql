-- Migration: Per-workspace enable state for reference (module) ontologies
-- Date: 2026-09-16
--
-- Mirrors app_configs. ontology_id is the stable catalog key
-- "<module>:<filename.ttl>" (e.g. "bfo:bfo-core.ttl") rather than the
-- absolute file path, which differs between a container and a checkout.
-- A file with no row here is disabled (resolved in workspace_catalog_seed).

CREATE TABLE IF NOT EXISTS ontology_configs (
    id VARCHAR(255) PRIMARY KEY,
    workspace_id VARCHAR(255) NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    ontology_id VARCHAR(1024) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_ontology_configs_workspace_ontology UNIQUE (workspace_id, ontology_id)
);

CREATE INDEX IF NOT EXISTS idx_ontology_configs_workspace ON ontology_configs(workspace_id);
CREATE INDEX IF NOT EXISTS idx_ontology_configs_ontology_id ON ontology_configs(ontology_id);
