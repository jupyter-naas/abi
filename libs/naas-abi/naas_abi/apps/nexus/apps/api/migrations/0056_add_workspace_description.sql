-- Migration: workspace description, group and feature overrides
-- Date: 2026-10-15
--
-- Description and group are edited in workspace Settings → General. The group
-- sorts workspaces in the workspace lists ("Others" when empty).
-- feature_overrides (JSON object, feature key -> bool) is edited in
-- Organization Settings → Workspaces. NULL means the deployment config
-- (nexus_config.feature_flags.workspace_overrides) applies.

ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS workspace_group VARCHAR(100);
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS feature_overrides TEXT;
