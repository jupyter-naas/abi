-- Migration: Add the per-workspace default coding repository

ALTER TABLE workspaces
    ADD COLUMN IF NOT EXISTS coding_default_repo_id VARCHAR;

COMMENT ON COLUMN workspaces.coding_default_repo_id IS
    'Default git repo (owner/name) cloned for new coding workspaces in this Nexus workspace; falls back to the configured CODING_REPO_ID when unset.';
