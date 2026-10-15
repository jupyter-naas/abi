-- Migration: workspace description and group
-- Date: 2026-10-15
--
-- Both are edited in workspace Settings → General. The group sorts workspaces
-- in the workspace lists ("Others" when empty).

ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS workspace_group VARCHAR(100);
