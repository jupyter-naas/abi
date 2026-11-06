# View as - AGENTS.md

## Purpose

An administrator who has just set up someone's access sees Nexus as that person sees it, in one of the
person's workspaces, without signing in as them and without being able to change anything. The server side of
the job: the record of a view, the routes that start and stop it, the identity every request of the browser then
runs under, the read-only and workspace limits, and the audit. The web (the picker, the banner, Stop) is
`apps/web`. What the view keeps private, the page loads that write and do nothing in it, the reads sent by POST, the
activity log and the apps opened in a view are "Private content" to "Apps opened in a view" below.

**Who may view as whom is IAM's**, core `services/iam/AGENTS.md` ("Viewing as a principal"): `iam:ViewAs` on
`<workspace container>/iam:view_as/<person>`, and the person holds no more than the viewer there. Nexus asks
(`iam.view_as_verdict`, `require_view_as`, in process, as `api` on behalf of the viewer) and adds no role check.

## Files

| File | Role |
|---|---|
| `port.py` | `ViewStore` (what a view keeps and reads in the database), `ViewIam` (what it asks of IAM), the records (`ViewRecord`, `Viewer`, `Person`, `WorkspaceRef`), the errors, `VIEW_LIFETIME` (15 minutes: the one place), and the reasons a view ends |
| `service.py` | `ViewAsService`: `workspaces`, `start`, `stop`, `running` (reads only), `resolve` (every request) |
| `confinement.py` | What a view answers: the read-only rule, the workspace rule, `ANSWERED_WITHOUT_A_WORKSPACE` (each route with its reason), `judge` |
| `reads_by_post.py` | `READS_BY_POST`: the reads Nexus takes by POST, one list, each entry with its reason and what a view does with it (read by the route matrix test and by the guard) |
| `active.py` | `viewing()`, `current_view()`, `use_view()`: the view of the request being served, in a `ContextVar` set by the identity middleware, for the code that must behave differently in a view |
| `views.py` | A view and a workspace as the JSON the web reads |
| `runtime.py` | `RUNTIME` builds the service (engine IAM, Nexus's database, `SqlAdminAuditLog(prefix="iam.")`, the links, a clock tests set); `running_view`, `is_viewing`, `end_on_sign_out`, `audited_open`; tests `configure` another |
| `adapters/secondary/sql.py` | `ViewStore` on `view_as_views` (migration `0069_view_as.sql`), `users`, `auth_sessions`, `workspaces`, `organizations` |
| `adapters/secondary/links.py` | `ViewLinks` on `apps/links.py`: revokes the links a view made when it ends |
| `adapters/secondary/engine.py` | `ViewIam` on the engine's IAM, as the viewer; the person's workspaces are `MEMBERSHIPS`' (a role held there, or the organization-wide one an organization's owner or admin holds) |
| `adapters/primary/view_as__primary_adapter__FastAPI.py` | `/api/iam/view-as` |
| `adapters/primary/view_as__primary_adapter__ASGI.py` | `ViewGuardMiddleware`: the read-only and workspace limits |
| `testing.py` | `MemoryViewStore`, `FakeViewIam`, `FakeViewLinks` |
| `full_app_testing.py`, `conftest.py` | The whole application behind the view's middleware over the test world (tests of private content, writes, the activity log and app links) |

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
  session) and the reads sent by POST that `READS_BY_POST` allows ("Reads sent by POST"). That includes
  `POST /api/settings-cache/refresh`, which the cache answers itself.
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

## Reads sent by POST

A few reads travel as POST (a query too structured for a URL). `reads_by_post.py` is the one list of them; the route
matrix test reads it (a write method that authorizes only a read must be on it) and so does the guard. Each entry says
what it reads (`reads`), and what a view does with it (`in_view`: `allowed` or `refused`, with `why_in_view`).

- **Allowed**, answered as the person: the graph reads (explorer, discovery, network, query, facets, triples export,
  the views' filter preview), the dataset query, `/api/search/private`, `/api/iam/admin/simulate`, and the links to the
  person's apps (`/api/apps/access-token`, `/api/apps/remote-grant`, `/api/app-projects/{slug}/preview-token`: "Apps
  opened in a view"); and, with their reasons, `/api/iam/admin/policies/validate` (a check of the text sent),
  `/api/sheets/evaluate` (a calculation in memory), `/api/search/topics/preview` and `/api/maps/layouts/preview`
  (and `feeds/preview`, its older name: a preview that stores nothing), and `/api/agents/sync`, which in a view only
  lists (the roster is never reconciled).
- **Refused** ("Read-only"): `/api/v1/chat/completions`, speech, transcription, `/api/apps/sso-token` (no portal
  sign-in), the export of a conversation (the person's, private), and `/api/graph/analyze` (an upload of the import
  flow, whose multipart body the guard does not read).
- **Held to the viewed workspace.** `workspace` says where an allowed read names it: `body` (a JSON object whose
  top-level `workspace_id` must be the viewed one; the guard reads the body, at most 8 MB, 413 beyond, and hands the
  app the same bytes), `query` (judged as a GET is) or none (`simulate`, `validate`: IAM decides for the person
  alone). A body that is not that object, names another workspace or none: "Outside this view".

## Private content

**Rule.** What belongs to the person alone is not shown in a view: IAM's personal types and `${principal.id}`
resources (`builtin.self`), and the Nexus rows owned by them alone. The workspace's shared content they may reach is
shown. In a view the list answers empty, and one item "not found" (404): the page opens, and the web says the content is
private to them (subtask 4), without asking the server.

| What | Route | In a view |
|---|---|---|
| Conversations | `GET /api/chat/conversations`, `…/{id}`, `/api/chat/ingestion-jobs/{id}`; the export (POST) | `[]`; 404; refused read-only |
| My Drive | `GET /api/files/…?scope=my_drive` (the list, a file, raw, PDF preview, archive: the slides, documents and sheets pages read it there) | an empty list; 404. The workspace's own drive is shown |
| Coding environments | `GET /api/coding-environments?workspace_id=`, `…/{id}`, `…/logs`, `…/access` | `[]`; 404 |
| Workflow runs | `GET /api/workspaces/{ws}/workflows/runs`, `…/{module}/runs/{id}` | `{"runs": []}`; 404 |
| Secrets | `GET /api/secrets/{workspace_id}` (names and values) | `[]` |
| Personal API keys | `GET /api/iam/api-keys` (on `ANSWERED_WITHOUT_A_WORKSPACE`: the account page opens) | `[]` |

Not on the list because confinement keeps them out (they are "Outside this view" and must stay off
`ANSWERED_WITHOUT_A_WORKSPACE`, or be blanked when added): `nexus:user_storage` (`/api/platform/storage`),
`discovery:run/${principal.id}/*` (agent runs: `/api/admin/system/agents/runs`), and the person's self rights of
`builtin.self`: the activity log of an actor, `iam:principal` reads, `iam:key` reads, and
`source_control:forge_user` (`EnsureUser`, `MintGitToken`: no GET of a view mints a git token or ensures a user).

A single-item route that names no workspace is "Outside this view" until it is listed, with its reason, on
`ANSWERED_WITHOUT_A_WORKSPACE` (the three listed above are, so they answer 404/`[]`, not 403).

## Page loads that write

A GET that stores something (a seed, a placement, a migration, a cache) does nothing in a view: the answer is what is
stored, as it is. Each asks `viewing()` (`active.py`) or takes a flag its primary adapter sets from it:

- **The Coder user**: `coding_environment`'s `_orchestrator_user` returns the user's id without `ensure_user`.
- **My Drive**: `files` skips the legacy-layout migration (`_migrate_legacy_layout`) and the drive's placement
  (`ensure_workspace_drive_placed`) in a view.
- **The maps' seed rows**: the layouts', basemaps' and feed layers' `list` (and `get`/`data_source` of a layer) take
  `seed=False`, which writes no seed, no initial feed or basemap decision and no default layer. In a view a workspace
  whose seeds have not been applied yet shows what is stored (none).
- **The topic cache**: `search/topics` places no cache, creates no generation and stores no entry in a view; the
  search is run, not cached.
- **The agents' roster**: `GET /api/agents/` and `/sync` never reconcile in a view.
- **A workspace's resource policies** (`workspace_resource_policies`: the graphs' and ontologies' policy): the first
  read of a workspace stores its configured policy; in a view `load_resource_policy` answers it without storing it.
- **The skills `/use` stamp and the analytics events** are POSTs, refused by the guard. The web's calls already ignore
  the refusal (`markSkillUsed` and `trackEvent` swallow a failed answer: nothing is shown, nothing is retried).

`no_writes_test.py` proves it: every GET route of the application that names the workspace (more than a hundred), and
every route on `ANSWERED_WITHOUT_A_WORKSPACE`, is called in a view against the test database and the test IAM; no
Nexus row but the view's own record and the viewer's session `last_seen_at`, and no IAM write (the store's revision),
changes. A control calls the same pages outside a view and expects the writes. A new GET that writes must ask
`viewing()` or this test fails.

## The activity log

`HttpActivityLogMiddleware` records an event per request. During a view the call is the person's, but the request is
the viewer's act: the event is recorded under the viewer, with the person and the workspace as the attribute
`view_as: {principal_id, workspace_id}`. Nothing is recorded as the person's activity.

## Apps opened in a view

The person's apps open in a view (`/api/apps/access-token`, `remote-grant`, and `app-projects/{slug}/preview-token`:
links of `apps/links.py`). The link is the person's, within these limits:

- **`not_after` is the view's end** (`mint_link` reads the view of the request; a link made from a link that a view
  made keeps its mark and the time of the link it came from).
- **Marked**: the key's description says which view made it (`view-as:<mark> <person> | …`, `port.tag_description`);
  `<mark>` is derived from the session and the start time, never the session's id. `open_link` reads it back
  (`OpenedLink.view`).
- **Revoked when the view ends** (Stop, sign-out, expired, no longer allowed): `ViewAsService._end` asks `ViewLinks`
  (`adapters/secondary/links.py` → `links.revoke_view_links`). A revocation that fails is logged and never keeps the
  view open: the link ends at the view's time anyway.
- **Read-only at the proxy**: `apps/remote/http_routes.py` forwards only GET and HEAD for a link a view made, and
  answers anything else "Read-only: you are viewing as <name>" (403), at the grant (`/app-remote/…`) and at the catalog
  URL (`/app-html/remote/…`, whose 307 would keep the method and whose fresh grant stays the view's).
- **Audited**: each open is `iam.view_as_open_app` (the viewer is the actor, the person the resource, the app and
  workspace the detail), around the minting (`runtime.audited_open`): fail-closed, no record, no link (503).

## Audit

Through the IAM admin's log (`SqlAdminAuditLog(prefix="iam.")`, `run_audited`), so the records show in Platform
settings › Roles & permissions › Audit, beside IAM's:

- `iam.view_as_start`: the actor is the viewer, the resource the person (IAM id), the detail the workspace, the
  end time and the groups source. **Fail-closed**: a `requested` record first, no record, no view (503). A refused
  start is a `requested` then a `failed` record (the exception type).
- `iam.view_as_stop`: the actor is the viewer, the resource the person, the detail `stop`, `sign-out`, `expired`
  or `no longer allowed`. Written after the end, never before: a record that cannot be written never keeps a
  view open (it is logged). An end is recorded when the server sees it, once.
- `iam.view_as_open_app`: the viewer, the person, the app and workspace. Fail-closed like the start.

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

- **Private content is blanked where the route answers, not by the guard.** Decision: each private route asks
  `viewing()` and answers `[]` or 404; the guard only decides which routes a view reaches. Consequences: the shape of an
  empty answer is the route's own (the page still opens), a single-item route that names no workspace needs an entry
  on `ANSWERED_WITHOUT_A_WORKSPACE` to be answered 404 and not 403, and a new personal route must be blanked with its
  own test (`private_content_test.py`).
- **The view of a request is a `ContextVar`.** Decision: `RequestIdentityMiddleware` sets it next to the call context
  (`active.py`), so deep code (a seed, a placement, the activity log, `mint_link`) needs no request passed down to it.
  Consequences: it follows the request into the threadpool and `asyncio.to_thread`, and never leaks to the next request.
- **A POST read names its workspace in its body, and the guard reads it.** Decision: confinement holds a body to the
  viewed workspace as it holds a query. Consequences: a body over 8 MB is refused (413), and a multipart read
  (`/api/graph/analyze`) is refused rather than judged.
- **A link made in a view is marked in IAM's key description, not in a table of Nexus.** Decision: the description
  (`view-as:<mark> …`) is what `authenticate_user_key` already answers, so no migration and no join at the proxy.
  Consequences: the person's key list shows it (a link, never a personal key), and the mark is a hash, never the
  session's id.

## Tests

```bash
uv run pytest libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/view_as --import-mode=importlib --no-cov -q
```

`service_test.py` (the use cases on fakes, the links' revocation, the audit of an open), `confinement_test.py` (every
route classified), `reads_by_post_test.py` (every read sent by POST classified, allowed ones held to the workspace,
refused ones read-only, the body read and handed on whole), `view_as_http_test.py` (a real IAM, Nexus's migrations on
SQLite, the identity and guard middleware and the routes: start, the workspaces, the person's identity and groups,
confinement, read-only, the cache, the WebSocket, the end, the audit, the upgrade). Over the whole application
(`full_app_testing.py`): `private_content_test.py` (each private route empty or not found in a view, and answering outside
one), `no_writes_test.py`, `activity_log_in_a_view_test.py`, `app_links_in_a_view_test.py` (the link's end, its
revocation at Stop, sign-out and expiry, the audit). `apps/remote/http_routes_test.py` covers the proxy.

The Nexus suites of this scope: view_as, iam (route matrix), chat, files, apps, secrets, api_keys, activity_log,
coding_environment, workflows, maps and search.

## Not done

- The web (the banner, the picker, "Private to <name>" on the private pages) is subtask 4.
- A view of the maps does not apply the deployment's seeds: a workspace that was never opened outside a view shows
  what is stored (no seeded layouts, basemaps or layers) until someone opens it.
- `/api/graph/analyze` (the import's upload) is refused in a view; its multipart body is not judged.
