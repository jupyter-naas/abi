-- YAML initializes assignments once. Administrator changes persist independently.
CREATE TABLE IF NOT EXISTS workspace_resource_policies (
    workspace_id VARCHAR NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    resource_kind VARCHAR(24) NOT NULL,
    policy TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    updated_by VARCHAR REFERENCES users(id) ON DELETE SET NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, resource_kind),
    CHECK (resource_kind IN ('ontologies', 'graphs'))
);
