-- Per-workspace search topics: overrides of built-in topics and custom ones.
CREATE TABLE IF NOT EXISTS search_topics (
    workspace_id VARCHAR NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    topic_id VARCHAR(48) NOT NULL,
    definition TEXT NOT NULL,
    updated_by VARCHAR REFERENCES users(id) ON DELETE SET NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, topic_id)
);
