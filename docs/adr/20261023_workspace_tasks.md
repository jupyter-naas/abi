# Workspace Tasks and shared database views

- **Status:** Accepted
- **Date:** 2026-10-23

## Context

Issue #1383 asks for a workspace-level task tracker in Nexus: tasks in six
fixed stages, weekly ISO-week iterations, a backlog, carry-over of unfinished
tasks, assignees from the workspace, comments and an activity history, shown
as a board. It must reuse the Notion-style database views of Nexus Apps (view tabs,
search, filter, sort, group, properties) rather than add a second toolbar.

The Apps database model was hard-wired to the app record type, and Nexus
features are gated per role through `feature_flags` (`role_baseline`, org and
workspace overrides), which until now only drove the frontend.

The feature is called **Tasks**: the workspace feature, its route, API, store,
tables and feature key are all named after tasks. **Board** is one layout of
those tasks (stage columns), next to Table, Gallery and Calendar, and the
generic `board` view type of the database view keeps its name.

## Decision

1. **New `tasks` feature key.** In the default catalog, granted to `owner` and
   `admin` only. Organizations and workspaces can open it to members through the
   existing overrides. Deployments that list `enabled_features` explicitly must
   add `tasks` to use it.
2. **The API enforces the flag.** Every `/api/tasks` route checks workspace
   access, then `caller_feature_flags(...)["tasks"]` for the caller's role, and
   answers 403 otherwise. Hiding the sidebar entry is not access control.
3. **New hexagonal domain `services/tasks/`.** Port (`TasksStorePort`,
   `TasksMemberDirectoryPort`), service, Postgres and in-memory adapters, and a
   FastAPI primary adapter. Migration `0059_add_tasks.sql` adds `task_iterations`,
   `tasks`, `task_comments` and `task_activity`, all scoped by `workspace_id`.
   Tasks live at `/api/tasks` and `/api/tasks/{task_id}`, next to
   `/api/tasks/iterations` and `/api/tasks/settings`.
4. **An iteration is a run of whole weeks keyed by its first day.** One ISO
   week by default; the length and start weekday come from the tasks settings
   (decision 7). Iterations never overlap and store their last day. The client
   sends its local date to get "the iteration of this date", so boundaries follow
   the user's timezone. A unique `(workspace_id, start_date)` makes creation
   idempotent across concurrent users. A task with no iteration is in the backlog.
6. **The page shows five scopes, not saved-view tabs.** Current, last and next
   iteration (Board layout by default: stage columns from Ready to Done; the
   default view is named "Current iteration"), Inbox (every task still in the
   Inbox stage, scheduled or not) and Backlog (triaged tasks without an
   iteration). The client loads every task of the workspace once
   (`GET /api/tasks` without a scope) into a shared store, so the tabs, the
   task drawer and the sidebar dashboard read the same rows and share one
   assignee filter. Dropping a card on a column changes its stage; dropping it on
   a tab moves it to that scope. Weeks other than the current one get their
   iteration when a task or a goal first needs it.
5. **The database view is extracted into `components/database-view/`.** It
   holds a generic schema (properties plus filter/search/sort/group pipeline),
   saved views per user in localStorage, the view bar and the layouts. Apps and
   Tasks both describe their rows with it. Properties may declare ordered
   `options` (stages, priorities) so grouping lists every option in order,
   including empty ones.

7. **Tasks settings per workspace, enforced by the API.** `GET/PUT
   /api/tasks/settings` (migration `0060_task_settings.sql`, JSON in
   `task_settings`) hold the iteration length (1–4 weeks) and start weekday,
   the stages (Inbox and Done are fixed system stages, custom ones go between),
   the priorities, the default stage of new iteration tasks and the suggested
   labels. Task stages and priorities are validated against them. Owners and
   admins save them; anyone with Tasks reads them. A new rhythm starts after
   the ongoing iteration (an anchor date), so existing iterations keep their
   dates and a short bridging iteration fills any gap. Removing a stage or
   priority that tasks still use is refused. Colors are palette names, mapped to
   theme-aware classes, not free hex values.

## Consequences

- Apps keeps its behavior and saved views (same storage key); its tests are
  unchanged.
- Iterations older than last week have no tab; their tasks stay reachable from
  the sidebar dashboard and the task drawer.
- Loading every task suits workspace-sized task lists; a very large workspace would
  need paging.
- Concurrent edits are last-write-wins. There is no real-time sync and no manual
  ordering within a column (cards follow the view's sort).
- Saved task views are per user and per browser, not shared across the
  workspace.
- Assignees are validated against the workspace member listing (explicit and
  organization-inherited members), so an assignee can be a member who cannot
  open Tasks under the default roles.
- Stage and priority keys are fixed once created (renaming changes the label
  only), so task history and saved filters keep working.
- Dependencies, estimates, notifications and the delivery / data & AI fields
  stay out of scope (#1384).
- The feature was renamed from Board to Tasks before release. Routes, API,
  feature key, tables and localStorage keys (`nexus.tasks.*`) were renamed
  without aliases. Only the sidebar keeps the old `board` id as a known
  earlier nav order and a retired panel id, so a stored layout still restores.
