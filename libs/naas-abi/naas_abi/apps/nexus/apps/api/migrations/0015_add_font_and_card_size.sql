-- Migration 0015: Font URL and login card size (reference: login.html)
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS font_url TEXT;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS login_card_max_width TEXT;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS login_card_padding TEXT;
