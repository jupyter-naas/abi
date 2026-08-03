-- Migration: Map each coding workspace (a Coder workspace) to the repo it was
-- cloned from, so the workspaces list can be scoped per-repo.
-- Date: 2026-06-29
--
-- Coder remains the source of truth for the workspace itself; this table only
-- records the (workspace -> repo) binding, which is set once at provision time
-- and never changes. Rows for deleted workspaces are harmless (the list filter
-- intersects with Coder's live workspace list) and are cleaned up on delete.

CREATE TABLE IF NOT EXISTS coding_environments (
    id VARCHAR(255) PRIMARY KEY,            -- Coder workspace UUID
    workspace_id VARCHAR(255) NOT NULL,     -- Nexus workspace id
    user_id VARCHAR(255) NOT NULL,          -- Nexus user id (provisioner)
    repo_id VARCHAR(255),                   -- "owner/name" of the cloned repo
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_coding_environments_ws_repo
    ON coding_environments(workspace_id, repo_id);
