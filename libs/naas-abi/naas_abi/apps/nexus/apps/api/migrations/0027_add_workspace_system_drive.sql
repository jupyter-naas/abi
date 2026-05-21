-- Migration: Add system_drive_enabled flag on workspaces

ALTER TABLE workspaces
    ADD COLUMN IF NOT EXISTS system_drive_enabled BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN workspaces.system_drive_enabled IS
    'When TRUE, workspace owners and admins can access the full object-storage tree (system drive). Both this flag and an admin/owner role are required.';
