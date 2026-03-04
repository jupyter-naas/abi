-- Add workspace-level theming fields
-- These allow each workspace to have its own branding (logo, colors, fonts)
-- separate from organization-level branding

ALTER TABLE workspaces
ADD COLUMN logo_url TEXT,
ADD COLUMN logo_emoji VARCHAR(10),
ADD COLUMN primary_color VARCHAR(20) DEFAULT '#22c55e',
ADD COLUMN accent_color VARCHAR(20),
ADD COLUMN background_color VARCHAR(20),
ADD COLUMN sidebar_color VARCHAR(20),
ADD COLUMN font_family VARCHAR(255);

-- Add some example comments for clarity
COMMENT ON COLUMN workspaces.logo_url IS 'URL to workspace logo image (optional)';
COMMENT ON COLUMN workspaces.logo_emoji IS 'Emoji icon for workspace (fallback if no logo URL)';
COMMENT ON COLUMN workspaces.primary_color IS 'Primary brand color for workspace UI (hex)';
COMMENT ON COLUMN workspaces.accent_color IS 'Accent/secondary color for hover states (hex)';
COMMENT ON COLUMN workspaces.background_color IS 'Custom background color (hex)';
COMMENT ON COLUMN workspaces.sidebar_color IS 'Custom sidebar background color (hex)';
COMMENT ON COLUMN workspaces.font_family IS 'Custom font family name';
