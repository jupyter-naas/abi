-- Migration 0009: Add logo_rectangle_url to organizations
-- Distinguishes square logos (icon/sidebar) from wide logos (login page/headers)
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS logo_rectangle_url TEXT;
