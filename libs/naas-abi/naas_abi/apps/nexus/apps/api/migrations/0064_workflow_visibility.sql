-- Workflows and pipelines a workspace's admins turned on or off for everyone in
-- it (workspace settings, Workflows). An item never switched is on; a hidden one
-- is refused when used, like an app or an agent turned off.
CREATE TABLE IF NOT EXISTS workflow_visibility (
    workspace_id VARCHAR(255) NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    type VARCHAR(32) NOT NULL,
    module_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, type, module_id, name)
);
