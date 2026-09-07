-- Desktop wallpaper URL for the workspace Home canvas.
ALTER TABLE workspaces
    ADD COLUMN IF NOT EXISTS background_image_url TEXT;
