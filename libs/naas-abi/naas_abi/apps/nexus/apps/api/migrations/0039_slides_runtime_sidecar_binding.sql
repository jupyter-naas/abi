-- Migration: Per-slug Slides Coder runtime binding + sidecar credentials
-- Date: 2026-07-30
--
-- Each Slides project (slug) gets a dedicated Coder workspace. Persist the
-- sidecar base URL + bearer secret so the Nexus Abi pane can bind
-- workspace filesystem tools the same way Continue does via JWT claims.

ALTER TABLE coding_environments
    ADD COLUMN IF NOT EXISTS label VARCHAR(255),
    ADD COLUMN IF NOT EXISTS sidecar_base VARCHAR(512),
    ADD COLUMN IF NOT EXISTS sidecar_secret VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_coding_environments_ws_user_label
    ON coding_environments(workspace_id, user_id, label);
