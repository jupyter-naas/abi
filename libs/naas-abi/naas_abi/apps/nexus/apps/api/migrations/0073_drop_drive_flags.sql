-- Migration: Drop the workspaces' drive flags (#1529), keeping them for conversion (#1590)
--
-- Who opens Platform Files and System Files is IAM's alone: Platform Files is
-- given with the workspace (Workspace settings > General, a platform group per
-- workspace), System Files is the platform admin's. Runs at every start.
--
-- PostgreSQL: while the columns exist, the flagged workspaces are first copied into
-- workspace_drive_flags_legacy, which the access_model_v1 migration (#1587) reads
-- through convert_legacy_drive_flags (services/iam/platform_files.py), then drops:
-- platform_drive_enabled becomes Platform Files read and write, system_drive_enabled
-- is reported and not converted. No flagged workspace, no table. Once the columns
-- are gone the block does nothing, so a deployment that ran 0073 before #1590 has
-- nothing to convert.
--
-- SQLite: the runner skips a DO block (SQLite has none), so nothing is kept there
-- and a flag set on a SQLite deployment is not converted: a platform admin sets the
-- workspace's Platform Files by hand. The drops are rewritten without IF EXISTS and
-- a column already gone is skipped.
--
-- The block keeps no inline comment (the runner joins its lines with spaces), and
-- reads the flags through EXECUTE: they are not planned once the columns are gone.
DO $$
DECLARE
    flagged BOOLEAN;
BEGIN
    IF (
        SELECT count(*) FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'workspaces'
        AND column_name IN ('platform_drive_enabled', 'system_drive_enabled')
    ) = 2 THEN
        EXECUTE 'SELECT EXISTS (SELECT 1 FROM workspaces WHERE platform_drive_enabled OR system_drive_enabled)'
            INTO flagged;
        IF flagged THEN
            CREATE TABLE IF NOT EXISTS workspace_drive_flags_legacy (
                workspace_id VARCHAR(255) PRIMARY KEY,
                platform_drive_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                system_drive_enabled BOOLEAN NOT NULL DEFAULT FALSE
            );
            EXECUTE 'INSERT INTO workspace_drive_flags_legacy '
                || 'SELECT id, platform_drive_enabled, system_drive_enabled FROM workspaces '
                || 'WHERE platform_drive_enabled OR system_drive_enabled '
                || 'ON CONFLICT (workspace_id) DO UPDATE SET '
                || 'platform_drive_enabled = EXCLUDED.platform_drive_enabled, '
                || 'system_drive_enabled = EXCLUDED.system_drive_enabled';
        END IF;
    END IF;
END $$;
ALTER TABLE workspaces DROP COLUMN IF EXISTS platform_drive_enabled;
ALTER TABLE workspaces DROP COLUMN IF EXISTS system_drive_enabled;
