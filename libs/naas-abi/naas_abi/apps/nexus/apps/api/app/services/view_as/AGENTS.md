# View as - AGENTS.md

## Purpose

An administrator who has just set up someone's access sees Nexus as that person sees it, in one of the
person's workspaces, without signing in as them and without being able to change anything. The server side of
the job: the record of a view, the routes that start and stop it, the identity every request of the browser then
runs under, the read-only and workspace limits, and the audit. The web (the picker, the banner, Stop) is
`apps/web`; private content, page loads that write and apps opened in a view are the next step (see "Not done").

**Who may view as whom is IAM's**, core `services/iam/AGENTS.md` ("Viewing as a principal"): `iam:ViewAs` on
`<workspace container>/iam:view_as/<person>`, and the person holds no more than the viewer there. Nexus asks
(`iam.view_as_verdict`, `require_view_as`, in process, as `api` on behalf of the viewer) and adds no role check.

## Files

| File | Role |
|---|---|
| `port.py` | `ViewStore` (what a view keeps and reads in the database), `ViewIam` (what it asks of IAM), the records (`ViewRecord`, `Viewer`, `Person`, `WorkspaceRef`), the errors, `VIEW_LIFETIME` (15 minutes: the one place), and the reasons a view ends |
| `service.py` | `ViewAsService`: `workspaces`, `start`, `stop`, `running` (reads only), `resolve` (every request) |
| `confinement.py` | What a view answers: the read-only rule, the workspace rule, `ANSWERED_WITHOUT_A_WORKSPACE` (each route with its reason), `judge` |
| `views.py` | A view and a workspace as the JSON the web reads |
| `runtime.py` | `RUNTIME` builds the service (engine IAM, Nexus's database, `SqlAdminAuditLog(prefix="iam.")`, a clock tests set); `running_view`, `is_viewing`, `end_on_sign_out`; tests `configure` another |
| `adapters/secondary/sql.py` | `ViewStore` on `view_as_views` (migration `0069_view_as.sql`), `users`, `auth_sessions`, `workspaces`, `organizations` |
| `adapters/secondary/engine.py` | `ViewIam` on the engine's IAM, as the viewer; the person's workspaces are `MEMBERSHIPS`' (a role held there, or the organization-wide one an organization's owner or admin holds) |
| `adapters/primary/view_as__primary_adapter__FastAPI.py` | `/api/iam/view-as` |
| `adapters/primary/view_as__primary_adapter__ASGI.py` | `ViewGuardMiddleware`: the read-only and workspace limits |
| `testing.py` | `MemoryViewStore`, `FakeViewIam` |

Wired elsewhere: `identity_events/middleware.py` (the identity of a request in a view), `main.py` (the guard),
`settings_cache/middleware.py` (no cache), `services/websocket/runtime.py` (no socket), the sign-out and
`/session` of `services/oidc`, and `GET /api/workspaces` and `…/slug/{slug}` (the viewed workspace only).

## Routes

Session only (`/api/iam/`: an API key never starts or carries a view, and neither does a bearer session token:
the view is on the browser's cookie session):

- `GET /api/iam/view-as/workspaces?principal_id=` the workspaces the person belongs to where IAM accepts a view
  by the caller: `[{id, name, organization: {id, name} | null}]`, empty when there are none (also for a person
  who has not signed in to Nexus). `principal_id` is the IAM id, as the person's page in Roles & permissions has it.
- `POST /api/iam/view-as` (`principal_id`, `workspace_id`) starts the view. IAM decides (403 with its message),
  audited first. Answers `{person: {id, name}, workspace: {id, name}, ends_at, groups_from}`; `groups_from` is
  the time of the sign-in session the person's groups were taken from, or null (stored groups only). 404 for a
  person who has no Nexus account or a workspace that does not exist, 409 while a view runs, 503 when the audit
  cannot be written (no record, no view).
- `DELETE /api/iam/view-as` ends the view (`{stopped: bool}`, audited). It needs no right: it gives one up.
- `GET /api/auth/oidc/session` adds `view` (as the POST answers it, or null), still about the viewer.

## The record

`view_as_views`, one row per session (`auth_sessions.id`), kept after it ends (`ended_at`) until the session's
next view replaces it: the viewer, the person (Nexus id and IAM principal id), the workspace and its container,
the person's identity provider groups and when they were recorded, and the start and end times. The names of
the person and the workspace are kept so the banner and the refusals need no lookup. A deleted user takes
their views with them (`ON DELETE CASCADE` through the session).

- **Groups** are IAM group ids, taken **at the start** from the person's most recent `auth_sessions` row
  (`group_ids`, ordered by `created_at`), with that row's `created_at` as `groups_from`; none for a person with
  no session. IAM checks exactly these, the view uses exactly these (the call's groups are these, IAM adds the
  stored ones), and the re-check at every request passes none more: nothing is read again.
- **15 minutes** is `VIEW_LIFETIME`. The clock is the runtime's.

## During a view

For a **cookie session** with a running view, `RequestIdentityMiddleware` makes the request the person's:
the credential and the `CallContext` together (user id, `on_behalf_of`, groups), so `AUTHZ.context(user)`,
`get_current_user` and every IAM decision answer the person; the call's container is the workspace's;
`request.state.nexus_session` stays the viewer's (CSRF, `/session`), and `nexus_view` and `nexus_viewer` are on
the request state. A bearer credential (an API key, a session token) never carries a view.

- **`iam:ViewAs` is decided again at every request**: one `authorize` as the viewer. A viewer who no longer holds
  it ends the view (recorded "no longer allowed") and the request is the viewer's.
- **A view past its end is ended** by the first request that sees it (recorded "expired"), and that request
  runs as the viewer. `running` is the read that records nothing (the WebSocket handshake asks it).
- **The person is named by their IAM principal id** everywhere (IAM calls, the audit resource, the re-check), whichever
  id the route was given: a Nexus id of an account of the old login finds the same person.
- **A view that cannot be verified names nobody** (IAM or the database failed): the request is `ANONYMOUS`, marked
  `nexus_view_unavailable`, and the guard answers every `/api` request 503. Never the viewer's request in its place:
  a browser that believes it is in a view must not write as the viewer. Stop and the sign-out still pass: they only give
  access up, and need no verification (they end the view or the session by the session's id).

`ViewGuardMiddleware` then judges every `/api` request (`confinement.judge`) before the settings cache:

- **Read-only.** Every method but GET, HEAD and OPTIONS is refused, 403 `{"detail": "Read-only: you are viewing
  as <name>"}`, apart from Stop and the sign-out (`POST /api/auth/oidc/logout`, which ends the view with the
  session). That includes `POST /api/settings-cache/refresh`, which the cache answers itself.
- **Confined.** A GET is answered when it names the viewed workspace: a path parameter or a `workspace_id` query
  parameter **that its route declares** (a `workspace_id` in the query of a route that takes none names nothing),
  every one of them the viewed workspace; or when its route is on `ANSWERED_WITHOUT_A_WORKSPACE`, each entry with
  its reason. Anything else is 403 "Outside this view: you are viewing as <name> in <workspace>".
- **`GET /api/workspaces`** lists the viewed workspace only, and `…/slug/{slug}` finds it only.
- **No WebSocket** (`websocket/runtime.py`): refused at the handshake, so no presence and no room.
- **No settings cache**: neither read nor filled (`nexus_view` on the scope's state).

`confinement_test.py` reads every route off the application like `iam/route_matrix_test.py`: each read route is
named, listed or outside; the list has no stale entry; a workspace is named `workspace_id` everywhere; the
organization pages and the platform's are outside.

## Audit

Through the IAM admin's log (`SqlAdminAuditLog(prefix="iam.")`, `run_audited`), so the records show in Platform
settings › Roles & permissions › Audit, beside IAM's:

- `iam.view_as_start`: the actor is the viewer, the resource the person (IAM id), the detail the workspace, the
  end time and the groups source. **Fail-closed**: a `requested` record first, no record, no view (503). A refused
  start is a `requested` then a `failed` record (the exception type).
- `iam.view_as_stop`: the actor is the viewer, the resource the person, the detail `stop`, `sign-out`, `expired`
  or `no longer allowed`. Written after the end, never before: a record that cannot be written never keeps a
  view open (it is logged). An end is recorded when the server sees it, once.

## Decisions

- **The guard is its own middleware, inside CORS.** Decision: the identity (the person's credential and context)
  is `RequestIdentityMiddleware`'s, because it is who the request is; the read-only and workspace refusals are
  `ViewGuardMiddleware`, added right outside the settings cache and inside `CORSMiddleware`. Consequences: a
  refusal carries the CORS headers, so a web app on another origin than the API (`abi dev`, `oidc_cookie_samesite:
  none`) can read "Read-only: ..." and show it; the guard runs before the cache, as it must (the cache answers
  `POST /api/settings-cache/refresh` itself); and it reads the view the identity middleware left on the scope's
  state, so it never looks it up twice.
- **A route is classified by the route it reaches, not by the text of the request.** Decision: `judge` finds the
  route (`scope["app"].router.routes`) and reads its declared parameters. Consequences: `?workspace_id=` on a route
  that ignores it cannot launder a request into the view; a route that names its workspace by another name is outside
  every view until it is renamed or listed (a test says so).
- **One row per session.** Decision: the session id is the key; a view that ended is replaced by the next one
  (audit keeps the history). Consequences: "one view per session" is the database's (a conflicting insert fails),
  not a check that could race.
- **The re-check is one `authorize`.** Decision: at every request IAM is asked `iam:ViewAs` on the person, as the viewer,
  not the whole "holds no more than the viewer" rule. Consequences: what the person holds is judged at the start; a
  grant made to them during the 15 minutes is not re-judged (the view ends at its end time at the latest).
- **The person is a Nexus user.** Decision: a person with no `users` row (never signed in to Nexus) is no one to view:
  the list is empty and a start is 404. Consequences: the context's user id is the Nexus id, as for every request.

## Tests

```bash
uv run pytest libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/view_as --import-mode=importlib --no-cov -q
```

`service_test.py` (the use cases on fakes), `confinement_test.py` (every route classified), `view_as_http_test.py`
(a real IAM, Nexus's migrations on SQLite, the identity and guard middleware and the routes: start, the workspaces,
the person's identity and groups, confinement, read-only, the cache, the WebSocket, the end, the audit, the
upgrade).

## Not done

Subtask "private content, page loads that write, apps opened in a view": the person's conversations, My Drive,
coding environments, workflow runs, the workspace's secrets and personal API keys stay private; the GET routes that
write (the Coder user, the My Drive migration, the maps' seed rows, the topic cache) do nothing in a view; reads sent
by POST, the activity log naming the viewer, and apps opened from a view (links that end with it). Until then every
POST is refused, and a GET that names the workspace is answered as the person.
