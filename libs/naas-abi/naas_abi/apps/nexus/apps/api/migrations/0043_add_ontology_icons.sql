-- Shared UI metadata for ontology terms and files; OWL source files stay untouched.
CREATE TABLE IF NOT EXISTS ontology_icons (
    workspace_id VARCHAR NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    target_key VARCHAR(64) NOT NULL,
    resource_kind VARCHAR(24) NOT NULL,
    resource_id TEXT NOT NULL,
    icon_name VARCHAR(160) NOT NULL,
    updated_by VARCHAR REFERENCES users(id) ON DELETE SET NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, target_key)
);
