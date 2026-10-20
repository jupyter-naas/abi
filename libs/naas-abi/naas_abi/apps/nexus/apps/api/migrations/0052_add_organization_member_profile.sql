-- Migration: Per-organization member profile
-- Date: 2026-10-14
--
-- Org admins edit a member's profile for their organization only. NULL means
-- "use the account value" (users.*), so existing members keep showing their
-- account profile until an admin edits them.

ALTER TABLE organization_members ADD COLUMN IF NOT EXISTS name VARCHAR(200);
ALTER TABLE organization_members ADD COLUMN IF NOT EXISTS avatar VARCHAR;
ALTER TABLE organization_members ADD COLUMN IF NOT EXISTS company VARCHAR(200);
ALTER TABLE organization_members ADD COLUMN IF NOT EXISTS job_title VARCHAR(100);
ALTER TABLE organization_members ADD COLUMN IF NOT EXISTS bio VARCHAR(2000);
