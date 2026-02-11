-- Migration 0011: Add login page styling options to organizations
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS login_card_color TEXT;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS login_border_radius TEXT;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS login_bg_image_url TEXT;
