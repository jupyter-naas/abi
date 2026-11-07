-- "View as": an administrator sees Nexus as another person in one workspace, read-only,
-- for 15 minutes at most (services/view_as). One row per browser session (the
-- auth_sessions row it runs on), ended with ended_at: Stop, sign-out or the end time.
-- The person's identity provider groups are the ones their most recent sign-in session
-- recorded, copied at the start (group_ids, groups_from): the view uses exactly the
-- groups IAM checked. The names are kept so the banner and the refusals need no lookup.
CREATE TABLE IF NOT EXISTS view_as_views (
    session_id VARCHAR(64) PRIMARY KEY REFERENCES auth_sessions(id) ON DELETE CASCADE,
    viewer_id VARCHAR(255) NOT NULL,
    person_id VARCHAR(255) NOT NULL,
    person_principal_id VARCHAR(255) NOT NULL,
    person_name VARCHAR(255) NOT NULL,
    workspace_id VARCHAR(255) NOT NULL,
    workspace_name VARCHAR(255) NOT NULL,
    container VARCHAR(512) NOT NULL,
    group_ids TEXT NOT NULL DEFAULT '[]',
    groups_from TIMESTAMP,
    started_at TIMESTAMP NOT NULL,
    ends_at TIMESTAMP NOT NULL,
    ended_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_view_as_views_viewer ON view_as_views(viewer_id);
