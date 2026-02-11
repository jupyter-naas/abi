-- Migration 0013: Add default_theme to organizations
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS default_theme TEXT;
