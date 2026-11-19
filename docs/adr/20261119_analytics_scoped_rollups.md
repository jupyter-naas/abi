# Analytics scoped by IAM to an organization or a workspace, computed from SQL rollups

- **Status:** Accepted
- **Date:** 2026-11-19

## Context

Nexus Analytics was a platform-wide app (`/analytics`) read by whoever held
`ReadAnalytics` on the platform singleton (epic #1533). It had no tenancy: every
figure and dropdown covered the whole platform, and the conversation detail and
export opened any conversation. Its computation did not scale either: a debounced,
per-process rebuild read the whole event log, rewrote the full history as one JSON
file in object storage, and every filtered request downloaded that file again.
`_upsert_refs` did a read-modify-write of `ref-*.json` on every event, without a lock.
The ingest route was guarded by the platform admin's `WriteAnalytics`, so regular
members' events were refused and never recorded. Periods were rolling windows in UTC.

The epic moves analytics into Organization settings and Workspace settings, each
limited to its scope, with four calendar periods in the organization's time zone.
Its backend is #1534, its web app #1535 (built against the API contract below) and
the removal of the app and its object-storage files #1536.

## Decision

1. **Two scopes, decided by IAM** (`nexus` catalog version 12, `catalog/platform.py`):

   | Action | Decided on | Default |
   |---|---|---|
   | `ReadOrganizationAnalytics` (`admin`) | the organization (`guard(..., workspace=None, org="org_id")`) | its owners and admins |
   | `ReadWorkspaceAnalytics` (`admin`) | the workspace (`guard(...)`) | its admins and owners, and the organization's through their org-wide role |
   | `ReadAnalyticsConversation` (`read`, type `analytics_conversation`, `policy_only`) | `<workspace>/nexus:analytics_conversation/<conversation>` (inline + `declares`) | nobody: a policy grants it |

   Without `ReadAnalyticsConversation` the conversations show metadata and counts,
   never messages, and the detail and export answer 403.

2. **The scope is resolved on the server** (`analytics__primary_adapter__scoped.py`),
   never from a query value, into an `AnalyticsScope` handed to the domain service:
   an organization is its workspaces (`workspaces.organization_id`) and its members
   (a role at its IAM container); a workspace is itself and who holds a role there or
   reaches it through an org-wide role (as its member list shows them). Only events
   of in-scope members in in-scope workspaces count (a platform admin passing through
   is not counted). A `workspace_id`, `user_id` or `conversation_id` outside the scope
   is 404. Emails are read from `users` at read time; events never store one.

3. **API contract** (shared with #1535). Under `/api/organizations/{org_id}/analytics`
   and `/api/workspaces/{workspace_id}/analytics`, with `period=today|yesterday|this_week|this_month`
   (default `today`, anything else 422), `workspace_id` (organization only) and `user_id`:
   `GET access` (`AnalyticsAccess {can_read, can_read_conversations, timezone}`, never 403),
   `overview` (+ `period: PeriodInfo`), `users`, `users/{user_id}`, `sessions`, `pages`,
   `workspaces` (organization only), `events?limit=` (≤ 500), `chats` (+ `can_read_messages`),
   `chat-analytics`, `chats/{conversation_id}` and `chats/{conversation_id}/export`.
   Bodies reuse the models of `services/analytics/port.py`; `SessionRow.user_id` and
   `ChatRow.user_id` are new. `PATCH /api/organizations/{org_id}` takes `timezone`.

4. **Organization time zone.** `organizations.timezone` (IANA, `NOT NULL DEFAULT 'UTC'`,
   migration `0073_organization_timezone.sql`), validated with `zoneinfo` (422
   otherwise). Periods are computed with `zoneinfo` (`analytics/periods.py`): today and
   yesterday hourly, this week (from Monday) and this month (from the 1st) daily, the
   current ones ending now; daylight saving days have 23 or 25 hourly buckets. A
   workspace uses its organization's zone (UTC with none).

5. **Ingest.** `POST /api/analytics/events` is any signed-in user's. The server sets
   `user_id` from the token (payload identity ignored), keeps `workspace_id` only for a
   member of it (IAM `GetWorkspace`, cached a minute) and stamps `organization_id` from
   the workspace's IAM container. It is written as `api` once the caller is
   authorized: a member's own rights never reach the log. `AnalyticsEventRecorded` gains
   the projected `organization_id`.

6. **Rollups in the Nexus database** (`0073_analytics_rollups.sql`), on PostgreSQL in
   production and SQLite in `abi dev`, through one SQLAlchemy adapter pair
   (`analytics__secondary_adapter__postgres.py`) behind two ports:
   `AnalyticsEventPort` (apply events, purge, jobs) and `AnalyticsQueryPort` (scoped reads).
   - `analytics_events`: the raw event, 45 days, keyed by sha256(user, tracker event id),
     indexed `(organization_id, timestamp)` and `(workspace_id, timestamp)`;
   - `analytics_hourly(bucket_hour, organization_id, workspace_id, user_id, event_name, page_path, count)`
     (pages);
   - `analytics_user_hourly(bucket_hour, organization_id, workspace_id, user_id, events, page_views)`:
     the same without the event and page keys, an order of magnitude fewer rows for the
     figures that count users, workspaces and totals;
   - `analytics_session(session_id, workspace_id, organization_id, user_id, started_at, ended_at, page_views, events, device, browser)`,
     one row per session and workspace so each scope counts its part;
   - `analytics_pages` (last title per path), `analytics_jobs` (job runs).

   An event is counted only when its raw row is new (`INSERT ... ON CONFLICT DO NOTHING
   RETURNING`), so applying is idempotent. One consumer cursor of the EventService log
   (`nexus.analytics.rollups`, `iter_query_for_consumer`) feeds it from every API
   process (`analytics/jobs.py`, every 5 s): the cursor hands each batch to one process,
   and a batch whose write fails is handed out again (cursor moved back unless another
   process read past it), which the idempotence makes harmless. Every 10 minutes one
   process replays the log's last six hours (`heal`), so a batch read by a process
   killed before writing it is counted after all (unless no heal succeeds for six
   hours, e.g. the Nexus database down that long). A deploy with no event log applies
   each ingest directly. An ingested event is at most 16 KB (413 beyond; checked once
   parsed, the API's 64 MiB body limit bounds the parsing).

7. **Reads** are one `GROUP BY` per figure over the rollups with
   `workspace_id IN (:scope) AND user_id IN (:members) AND bucket_hour/started_at in the period`
   (plus `organization_id = :org` for an organization, so events recorded while a
   workspace belonged to another organization stay there). Buckets are mapped to the
   zone's slots with a portable `CASE` over the slot boundaries. No request reads the
   whole history; there is no cache.

8. **Chat analytics are SQL aggregates** of `conversations`/`messages` in the scope.
   The chat adapter writes a message's `feedback`, `feedback_type` (columns of
   `messages`) and the tools it called (`message_tools`) whenever it writes the
   message's metadata (`chat/adapters/secondary/message_facts.py`, migration
   `0073_message_facts.sql`); nothing parses `metadata` at read time.

9. **Backfill and retention.** Once (`analytics_jobs` `backfill_v1`, claimed for an
   hour so one process runs it): the log's and the legacy object-storage events of the
   last 45 days are applied, the organization stamped from the workspace; then the
   messages of the last 45 days get their facts (`message_facts_v1`, also claimed). Daily, across
   processes (`claim_job`): raw `analytics_events` older than 45 days are deleted; the
   rollups stay. After the backfill, once (`legacy_storage_cleanup_v1`, claimed), the
   removed app's object-storage files are deleted (#1536, see Consequences).

## Consequences

- Analytics follow the organization: an admin sees their organization's members in
  their organization's workspaces and nothing else; a member of another organization
  never appears. Regular members' events are now recorded.
- **Removed (#1536):** the Analytics app (`naas_abi/apps/analytics/`, so it leaves the
  Apps catalog), its web page and the `/api/analytics/*` Next proxies (`/analytics` now
  leads to the current organization's Analytics section, or is a 404), the platform-wide
  reads (`overview`, `users`, `sessions`, `pages`, `workspaces`, `events`, `chats`,
  `chat-analytics`, `scenarios`, `metadata`, `rebuild`), the object-storage storage port
  with its JSON adapters, the rebuild and its scheduler, `_upsert_refs` and the
  scenarios. What stays of `/api/analytics` is the tracker's ingest; with an event log it
  only appends to it, without one it applies the event to the rollups. The chat's like
  and dislike moved to `PATCH /api/chat/conversations/{id}/messages/{id}/feedback`
  (`UpdateConversation` on the owner's conversation; it was the platform admin's
  `WriteAnalytics`, so other users' feedback was refused). `ReadAnalytics` and
  `WriteAnalytics` stay declared, deprecated and asked by no route (catalog 13), since
  IAM refuses a catalog dropping an action a policy may still name. Once the backfill
  is done, one process (claimed, `legacy_storage_cleanup_v1`) deletes the app's files
  under `naas_abi/nexus/analytics/` (`analytics/legacy_storage.py`): the aggregates,
  the `ref-*.json` directories, `metadata.json` and the raw `events/*`. The backfill
  reads those events first and is not recorded as done if the storage cannot be read,
  so nothing is deleted that was not replayed.
- The EventService log stays the source of truth and keeps its own retention (the
  PostgreSQL adapter archives after 7 days); the 45-day window is the Nexus raw table's.
  The backfill cannot replay what the log already archived.
- Hourly rollups are UTC hours: in a zone whose offset is not a whole hour (Asia/Kolkata,
  Asia/Kathmandu) a bucket straddling a local boundary counts in the slot it starts in.
- Seeded benchmark (`analytics/benchmark.py`: PostgreSQL 17 in a container with its
  default 128 MB `shared_buffers`, 1M events of the current month across 10
  organizations of 10 workspaces, 20 members each, 20 reads per figure after a
  warm-up): the slowest figure is an organization's `this_month` overview, 232 ms p50 /
  277 ms p95 (one workspace's: 44 ms p50 / 211 ms p95); every other figure is under
  110 ms p95. Before `analytics_user_hourly` that overview was 0.9 s / 1.1 s. The
  benchmark times the domain service and its SQL: not the scope's resolution (IAM, in
  memory, cached 15 s) nor HTTP, and its chat tables are empty. A larger organization
  or month is the first place to look if reads grow: a daily rollup per user, or a
  short cache keyed by scope, period and filters.
- **Alternatives rejected:** DuckDB/Parquet on MinIO (a new dependency and a second
  write path, no concurrent writer); TimescaleDB continuous aggregates or ClickHouse
  (new infrastructure a one-month window does not need); per-request aggregation of the
  raw log (unbounded); keeping the consumer cursor beside the rollups instead of the
  EventService's (exactly-once without idempotence, but a second cursor nobody else
  sees, and the archive job waits on the EventService's).
