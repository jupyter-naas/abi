-- Add abi_servers table
CREATE TABLE IF NOT EXISTS abi_servers (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    name TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    api_key TEXT,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    CONSTRAINT uq_workspace_endpoint UNIQUE (workspace_id, endpoint)
);

-- Add index
CREATE INDEX IF NOT EXISTS idx_abi_servers_workspace_id ON abi_servers(workspace_id);
