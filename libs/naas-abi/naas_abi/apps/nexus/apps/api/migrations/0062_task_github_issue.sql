-- Migration: link a task to a GitHub issue
-- Date: 2026-10-24
--
-- A task may point to one GitHub issue (its URL); empty when it has none.

ALTER TABLE tasks ADD COLUMN IF NOT EXISTS github_issue_url VARCHAR(500) NOT NULL DEFAULT '';
