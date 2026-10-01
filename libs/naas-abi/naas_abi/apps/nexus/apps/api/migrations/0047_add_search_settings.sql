-- Per-workspace search settings: feature and web-engine scopes switched off.
CREATE TABLE IF NOT EXISTS search_settings (
    workspace_id VARCHAR NOT NULL PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
    settings TEXT NOT NULL,
    updated_by VARCHAR REFERENCES users(id) ON DELETE SET NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
