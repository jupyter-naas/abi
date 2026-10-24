-- Migration: task events for the workspace feed
-- Date: 2026-10-24
--
-- task_activity becomes the workspace's task event log, shown in the sidebar:
-- events keep the task's title and outlive the task (no foreign key to tasks),
-- so a deletion still reads "Ada deleted Write the spec". Comments can reply to
-- a comment; replies are removed with it.

ALTER TABLE task_activity ADD COLUMN IF NOT EXISTS task_title VARCHAR(300) NOT NULL DEFAULT '';

ALTER TABLE task_activity DROP CONSTRAINT IF EXISTS task_activity_task_id_fkey;

CREATE INDEX IF NOT EXISTS idx_task_activity_workspace_created
    ON task_activity (workspace_id, created_at);

ALTER TABLE task_comments ADD COLUMN IF NOT EXISTS parent_id VARCHAR(48) REFERENCES task_comments(id) ON DELETE CASCADE;

-- Events recorded before titles were kept: name them after their task.
UPDATE task_activity SET task_title = (SELECT title FROM tasks WHERE tasks.id = task_activity.task_id) WHERE task_title = '' AND EXISTS (SELECT 1 FROM tasks WHERE tasks.id = task_activity.task_id);
