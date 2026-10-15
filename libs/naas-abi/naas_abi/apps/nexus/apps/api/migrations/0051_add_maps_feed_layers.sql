-- Map layers: views on a feed (maps_layouts row) — title, icon, color, order and
-- the feature types (classLabel) they keep. A feed always has at least one layer.
CREATE TABLE IF NOT EXISTS maps_feed_layers (
    workspace_id VARCHAR NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    layer_id VARCHAR(48) NOT NULL,
    feed_id VARCHAR(48) NOT NULL,
    definition TEXT NOT NULL,
    updated_by VARCHAR REFERENCES users(id) ON DELETE SET NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, layer_id)
);
CREATE INDEX IF NOT EXISTS ix_maps_feed_layers_feed ON maps_feed_layers (workspace_id, feed_id);
