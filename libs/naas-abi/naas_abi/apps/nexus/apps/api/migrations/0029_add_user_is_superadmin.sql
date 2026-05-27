-- Migration: Add is_superadmin flag on users

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS is_superadmin BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN users.is_superadmin IS
    'When TRUE, the user has platform-wide admin access (e.g. live event stream). Toggled via the users section of config.yaml.';
