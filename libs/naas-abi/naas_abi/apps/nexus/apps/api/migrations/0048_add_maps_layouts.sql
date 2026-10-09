-- Per-workspace Maps layouts (SPARQL pin layers) and which layouts are hidden.
CREATE TABLE IF NOT EXISTS maps_layouts (
    workspace_id VARCHAR NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    layout_id VARCHAR(48) NOT NULL,
    definition TEXT NOT NULL,
    updated_by VARCHAR REFERENCES users(id) ON DELETE SET NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, layout_id)
);

CREATE TABLE IF NOT EXISTS maps_settings (
    workspace_id VARCHAR PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
    settings TEXT NOT NULL,
    updated_by VARCHAR REFERENCES users(id) ON DELETE SET NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
