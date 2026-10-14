-- Migration: users.company -> users.organization
-- Date: 2026-10-14
--
-- The account field is labelled "Organization" in Account Settings > Profile.
-- organization_members.company (a member's profile in one organization) is
-- unchanged. Re-runs are skipped by the migration runner once applied.

ALTER TABLE users RENAME COLUMN company TO organization;
