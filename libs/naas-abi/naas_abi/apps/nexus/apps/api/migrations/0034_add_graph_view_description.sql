-- Migration: Add a free-text description to graph views (explains what a view answers)

ALTER TABLE graph_views
    ADD COLUMN IF NOT EXISTS description TEXT;

COMMENT ON COLUMN graph_views.description IS
    'Free-text description of what the saved view is trying to answer. NULL = none.';
