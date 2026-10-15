-- Migration: organization member profile fields
-- Date: 2026-10-14
--
-- organization_members.company -> organization (same name as users.organization),
-- plus service line, country and interest, set by org admins in
-- Organization Settings > Users > <user>. Re-runs are skipped once applied.

ALTER TABLE organization_members RENAME COLUMN company TO organization;
ALTER TABLE organization_members ADD COLUMN IF NOT EXISTS service_line VARCHAR(200);
ALTER TABLE organization_members ADD COLUMN IF NOT EXISTS country VARCHAR(100);
ALTER TABLE organization_members ADD COLUMN IF NOT EXISTS interest VARCHAR(1000);
