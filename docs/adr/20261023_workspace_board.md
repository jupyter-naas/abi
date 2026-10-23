# Workspace project board and shared database views

- **Status:** Accepted
- **Date:** 2026-10-23

## Context

Issue #1383 asks for a workspace-level project board in Nexus: tasks in six
fixed stages, weekly ISO-week iterations, a backlog, carry-over of unfinished
tasks, assignees from the workspace, comments and an activity history. The
board must reuse the Notion-style database views of Nexus Apps (view tabs,
search, filter, sort, group, properties) rather than add a second toolbar.

The Apps database model was hard-wired to the app record type, and Nexus
features are gated per role through `feature_flags` (`role_baseline`, org and
workspace overrides), which until now only drove the frontend.

## Decision

1. **New `board` feature key.** In the default catalog, granted to `owner` and
   `admin` only. Organizations and workspaces can open it to members through the
   existing overrides. Deployments that list `enabled_features` explicitly must
   add `board` to use it.
2. **The API enforces the flag.** Every `/api/board` route checks workspace
   access, then `caller_feature_flags(...)["board"]` for the caller's role, and
   answers 403 otherwise. Hiding the sidebar entry is not access control.
3. **New hexagonal domain `services/board/`.** Port (`BoardStorePort`,
   `BoardMemberDirectoryPort`), service, Postgres and in-memory adapters, and a
   FastAPI primary adapter. Migration `0059_add_board.sql` adds iterations, tasks,
   comments and activity, all scoped by `workspace_id`.
4. **An iteration is one ISO week keyed by its Monday.** The client sends its
   local date to get "the iteration of this week", so week boundaries follow the
   user's timezone. A unique `(workspace_id, start_date)` makes creation
   idempotent across concurrent users. A task with no iteration is in the backlog.
5. **The database view is extracted into `components/database-view/`.** It
   holds a generic schema (properties plus filter/search/sort/group pipeline),
   saved views per user in localStorage, the view bar and the layouts. Apps and
   Board both describe their rows with it. Properties may declare ordered
   `options` (stages, priorities) so grouping lists every option in order,
   including empty ones.

## Consequences

- Apps keeps its behavior and saved views (same storage key); its tests are
  unchanged.
- Concurrent edits are last-write-wins. There is no real-time sync and no manual
  ordering within a column (cards follow the view's sort).
- Saved board views are per user and per browser, not shared across the
  workspace.
- Assignees are validated against the workspace member listing (explicit and
  organization-inherited members), so an assignee can be a member who cannot
  open the board under the default roles.
- Custom stages, dependencies, estimates, notifications and the delivery /
  data & AI fields stay out of scope (#1384).
