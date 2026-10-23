-- Migration: board settings and iterations longer than a week
-- Date: 2026-10-23
--
-- Each workspace may store its board configuration (iteration length and
-- start day, stages, priorities, suggested labels) as JSON. Iterations record
-- their last day; rows made before this migration span one week (NULL).

CREATE TABLE IF NOT EXISTS board_settings (
    workspace_id VARCHAR PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
    data TEXT NOT NULL DEFAULT '{}',
    updated_by VARCHAR REFERENCES users(id) ON DELETE SET NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE board_iterations ADD COLUMN IF NOT EXISTS end_date DATE;
