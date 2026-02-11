-- Migration: Set default theme for organizations to 'light'
-- This ensures all organizations have a theme, and new ones default to light

-- Set existing NULL themes to 'light'
UPDATE organizations 
SET default_theme = 'light' 
WHERE default_theme IS NULL OR default_theme = '';

-- Add default value for future inserts
ALTER TABLE organizations 
ALTER COLUMN default_theme SET DEFAULT 'light';

-- Add check constraint to ensure only valid themes
ALTER TABLE organizations
ADD CONSTRAINT organizations_default_theme_check 
CHECK (default_theme IN ('light', 'dark', 'system') OR default_theme IS NULL);
