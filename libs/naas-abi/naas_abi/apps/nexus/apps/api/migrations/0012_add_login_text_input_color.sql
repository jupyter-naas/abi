-- Migration 0012: Add login text and input color options
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS login_text_color TEXT;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS login_input_color TEXT;
