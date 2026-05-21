-- Migration: Per-workspace enable state for marketplace apps
-- Date: 2026-05-21

CREATE TABLE IF NOT EXISTS app_configs (
    id VARCHAR(255) PRIMARY KEY,
    workspace_id VARCHAR(255) NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    app_id VARCHAR(512) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_app_configs_workspace_app UNIQUE (workspace_id, app_id)
);

CREATE INDEX IF NOT EXISTS idx_app_configs_workspace ON app_configs(workspace_id);
CREATE INDEX IF NOT EXISTS idx_app_configs_app_id ON app_configs(app_id);
