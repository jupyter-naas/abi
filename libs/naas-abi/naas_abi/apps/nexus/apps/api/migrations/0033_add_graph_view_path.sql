-- Migration: Add folder path to graph views (filesystem-style organization, AUDIT §7b.8)

ALTER TABLE graph_views
    ADD COLUMN IF NOT EXISTS path VARCHAR(1024) NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_graph_views_workspace_path ON graph_views(workspace_id, path);

COMMENT ON COLUMN graph_views.path IS
    'Folder path for organizing views, e.g. "Sales/Leads/Active". Empty = root. Folder rename = prefix-rewrite across rows in one transaction.';
