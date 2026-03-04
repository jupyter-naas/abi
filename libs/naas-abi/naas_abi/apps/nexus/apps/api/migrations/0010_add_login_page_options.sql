-- Migration 0010: Add login page display options to organizations
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS show_terms_footer BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS show_powered_by BOOLEAN NOT NULL DEFAULT TRUE;
