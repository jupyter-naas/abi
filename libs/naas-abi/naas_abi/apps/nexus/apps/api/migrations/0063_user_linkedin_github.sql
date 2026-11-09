-- Migration: a user's LinkedIn profile URL and GitHub handle
-- Date: 2026-10-29
--
-- Typed in Account Settings > Profile. The LinkedIn URL names the user's own
-- person when their LinkedIn export is imported into People Intelligence.
-- Empty (NULL) when the user has not set them.

ALTER TABLE users ADD COLUMN IF NOT EXISTS linkedin_url VARCHAR(500);
ALTER TABLE users ADD COLUMN IF NOT EXISTS github_handle VARCHAR(100);
