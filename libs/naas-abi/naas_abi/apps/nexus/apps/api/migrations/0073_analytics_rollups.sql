-- Analytics computed from SQL rollups (epic #1533, docs/adr/20261119_analytics_scoped_rollups.md).
--
-- The tracker's events stay in the EventService log (AnalyticsEventRecorded). One
-- consumer applies each of them once: the raw row (kept 45 days, for the event lists),
-- an hourly count and its session. Reads are one GROUP BY over these tables, scoped to
-- an organization's or a workspace's ids. Empty strings stand for "none" in key columns.

CREATE TABLE IF NOT EXISTS analytics_events (
    event_key VARCHAR(64) PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    organization_id VARCHAR NOT NULL DEFAULT '',
    workspace_id VARCHAR NOT NULL DEFAULT '',
    user_id VARCHAR NOT NULL DEFAULT '',
    session_id VARCHAR(64) NOT NULL DEFAULT '',
    event_name VARCHAR(64) NOT NULL,
    page_path VARCHAR(512) NOT NULL DEFAULT '',
    payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_analytics_events_org_ts ON analytics_events (organization_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_analytics_events_ws_ts ON analytics_events (workspace_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_analytics_events_ts ON analytics_events (timestamp);

CREATE TABLE IF NOT EXISTS analytics_hourly (
    bucket_hour TIMESTAMP NOT NULL,
    organization_id VARCHAR NOT NULL DEFAULT '',
    workspace_id VARCHAR NOT NULL DEFAULT '',
    user_id VARCHAR NOT NULL DEFAULT '',
    event_name VARCHAR(64) NOT NULL,
    page_path VARCHAR(512) NOT NULL DEFAULT '',
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (bucket_hour, organization_id, workspace_id, user_id, event_name, page_path)
);
CREATE INDEX IF NOT EXISTS idx_analytics_hourly_org_hour ON analytics_hourly (organization_id, bucket_hour);
CREATE INDEX IF NOT EXISTS idx_analytics_hourly_ws_hour ON analytics_hourly (workspace_id, bucket_hour);

-- The same counts per user, without the event and page keys (users, workspaces, totals).
CREATE TABLE IF NOT EXISTS analytics_user_hourly (
    bucket_hour TIMESTAMP NOT NULL,
    organization_id VARCHAR NOT NULL DEFAULT '',
    workspace_id VARCHAR NOT NULL DEFAULT '',
    user_id VARCHAR NOT NULL DEFAULT '',
    events INTEGER NOT NULL DEFAULT 0,
    page_views INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (bucket_hour, organization_id, workspace_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_analytics_user_hourly_org_hour ON analytics_user_hourly (organization_id, bucket_hour);
CREATE INDEX IF NOT EXISTS idx_analytics_user_hourly_ws_hour ON analytics_user_hourly (workspace_id, bucket_hour);

CREATE TABLE IF NOT EXISTS analytics_session (
    session_id VARCHAR(64) NOT NULL,
    workspace_id VARCHAR NOT NULL DEFAULT '',
    organization_id VARCHAR NOT NULL DEFAULT '',
    user_id VARCHAR NOT NULL DEFAULT '',
    started_at TIMESTAMP NOT NULL,
    ended_at TIMESTAMP NOT NULL,
    page_views INTEGER NOT NULL DEFAULT 0,
    events INTEGER NOT NULL DEFAULT 0,
    device VARCHAR(64),
    browser VARCHAR(64),
    PRIMARY KEY (session_id, workspace_id)
);
CREATE INDEX IF NOT EXISTS idx_analytics_session_org_started ON analytics_session (organization_id, started_at);
CREATE INDEX IF NOT EXISTS idx_analytics_session_ws_started ON analytics_session (workspace_id, started_at);

-- The last title seen for a page, per organization and workspace like the hourly counts:
-- a title any user sends shows only in the scope it was recorded in. (An earlier draft
-- of this migration keyed titles by path alone in analytics_pages: dropped, titles are
-- seen again with the next page views.)
DROP TABLE IF EXISTS analytics_pages;
CREATE TABLE IF NOT EXISTS analytics_page_titles (
    organization_id VARCHAR NOT NULL DEFAULT '',
    workspace_id VARCHAR NOT NULL DEFAULT '',
    page_path VARCHAR(512) NOT NULL,
    page_title VARCHAR(512) NOT NULL DEFAULT '',
    PRIMARY KEY (organization_id, workspace_id, page_path)
);

-- The removed analytics app's events a legacy replay counted (analytics_events.event_key):
-- every one of them goes to the rollups whatever its age, and those past the 45 days of
-- raw rows have no other trace, so a second replay (before the files are deleted) skips them.
CREATE TABLE IF NOT EXISTS analytics_legacy_replayed (
    event_key VARCHAR(64) PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS analytics_jobs (
    name VARCHAR(64) PRIMARY KEY,
    last_run_at TIMESTAMP NOT NULL
);
