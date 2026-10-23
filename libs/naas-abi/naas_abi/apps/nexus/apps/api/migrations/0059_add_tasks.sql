-- Migration: workspace tasks (weekly iterations, tasks, comments, activity)
-- Date: 2026-10-23
--
-- An iteration is one ISO week of a workspace, keyed by its Monday.
-- A task without an iteration sits in the backlog. Labels and assignees are
-- JSON lists of strings; activity values are JSON.

CREATE TABLE IF NOT EXISTS task_iterations (
    id VARCHAR(48) PRIMARY KEY,
    workspace_id VARCHAR NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    start_date DATE NOT NULL,
    goal VARCHAR(200) NOT NULL DEFAULT '',
    created_by VARCHAR REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR REFERENCES users(id) ON DELETE SET NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (workspace_id, start_date)
);

CREATE TABLE IF NOT EXISTS tasks (
    id VARCHAR(48) PRIMARY KEY,
    workspace_id VARCHAR NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    iteration_id VARCHAR(48) REFERENCES task_iterations(id) ON DELETE SET NULL,
    title VARCHAR(300) NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    stage VARCHAR(32) NOT NULL DEFAULT 'inbox',
    project VARCHAR(120) NOT NULL DEFAULT '',
    priority VARCHAR(16),
    due_date DATE,
    labels TEXT NOT NULL DEFAULT '[]',
    assignee_ids TEXT NOT NULL DEFAULT '[]',
    archived_at TIMESTAMP,
    created_by VARCHAR REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR REFERENCES users(id) ON DELETE SET NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tasks_workspace_iteration
    ON tasks (workspace_id, iteration_id);

CREATE TABLE IF NOT EXISTS task_comments (
    id VARCHAR(48) PRIMARY KEY,
    workspace_id VARCHAR NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    task_id VARCHAR(48) NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    author_id VARCHAR REFERENCES users(id) ON DELETE SET NULL,
    body TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_task_comments_task
    ON task_comments (task_id);

CREATE TABLE IF NOT EXISTS task_activity (
    id VARCHAR(48) PRIMARY KEY,
    workspace_id VARCHAR NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    task_id VARCHAR(48) NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    actor_id VARCHAR REFERENCES users(id) ON DELETE SET NULL,
    field VARCHAR(32) NOT NULL,
    old_value TEXT,
    new_value TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_task_activity_task
    ON task_activity (task_id);
