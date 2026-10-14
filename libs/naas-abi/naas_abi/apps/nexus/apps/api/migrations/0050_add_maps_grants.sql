-- Which workspaces may use a Maps layer or basemap (Settings → Maps → Access).
-- owner_workspace_id '' = deployment item (seed); workspace_ids NULL = every workspace,
-- else a JSON array of workspace ids. No row = default (deployment: all; custom: owner only).
CREATE TABLE IF NOT EXISTS maps_grants (
    kind VARCHAR(16) NOT NULL,
    item_id VARCHAR(48) NOT NULL,
    owner_workspace_id VARCHAR NOT NULL DEFAULT '',
    workspace_ids TEXT,
    updated_by VARCHAR REFERENCES users(id) ON DELETE SET NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (kind, item_id, owner_workspace_id)
);
