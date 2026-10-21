-- Migration: users.role -> users.job_title
-- Date: 2026-10-14
--
-- users.role was the job title typed in Account Settings > Profile, not an
-- access role (access roles live on organization_members / workspace_members).
-- Re-runs are skipped by the migration runner once applied.

ALTER TABLE users RENAME COLUMN role TO job_title;
