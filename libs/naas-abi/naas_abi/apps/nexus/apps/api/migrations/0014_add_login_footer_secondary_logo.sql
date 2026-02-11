-- Migration 0014: Custom login footer text, secondary logo, and logo separator (reference: login.html)
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS login_footer_text TEXT;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS secondary_logo_url TEXT;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS show_logo_separator BOOLEAN NOT NULL DEFAULT FALSE;
