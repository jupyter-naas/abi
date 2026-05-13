-- Migration: Add platform_drive_enabled flag on workspaces

ALTER TABLE workspaces
    ADD COLUMN IF NOT EXISTS platform_drive_enabled BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN workspaces.platform_drive_enabled IS
    'When TRUE, members of this workspace can read/write the shared platform-drive tree under naas_abi/platform-drive.';
