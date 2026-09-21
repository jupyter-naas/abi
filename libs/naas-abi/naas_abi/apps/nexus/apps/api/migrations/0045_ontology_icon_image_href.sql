-- Allow image URLs and upload paths on shared object icons.
-- @dialect: postgresql
-- SQLite treats VARCHAR(n) as TEXT, so this is a no-op there.

ALTER TABLE ontology_icons ALTER COLUMN icon_name TYPE TEXT;
