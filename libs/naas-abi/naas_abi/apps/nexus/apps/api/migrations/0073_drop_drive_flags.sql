-- Migration: Drop the workspaces' drive flags (#1529)
--
-- Who opens Platform Files and System Files is IAM's alone: Platform Files is
-- nobody's until a policy at the platform grants it, System Files the platform
-- admin's. The flags that opened them per workspace go, with what they held: no
-- upgrade keeps that access (the release notes say so). Runs at every start: on
-- PostgreSQL IF EXISTS makes it a no-op once applied; on SQLite the runner drops
-- IF EXISTS and skips a column already gone.
ALTER TABLE workspaces DROP COLUMN IF EXISTS platform_drive_enabled;
ALTER TABLE workspaces DROP COLUMN IF EXISTS system_drive_enabled;
