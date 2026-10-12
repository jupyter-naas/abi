-- Per-workspace Maps basemaps: definition (JSON renderer config) and preview image bytes.
-- Hidden basemap ids, layer colors and applied seeds live in maps_settings.settings (JSON).
CREATE TABLE IF NOT EXISTS maps_basemaps (
    workspace_id VARCHAR NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    basemap_id VARCHAR(48) NOT NULL,
    definition TEXT NOT NULL,
    preview BYTEA,
    preview_content_type VARCHAR(32),
    preview_version INTEGER NOT NULL DEFAULT 0,
    updated_by VARCHAR REFERENCES users(id) ON DELETE SET NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, basemap_id)
);
