# AGENTS.md

This is the README for coding agents working in NEXUS, the multi-tenant multi-LLM agent platform at `naas_abi/apps/nexus/`. Read it for intent and tradeoffs first; use the reference blocks when you need exact commands or paths.

NEXUS is vendored inside the ABI monorepo at `libs/naas-abi/naas_abi/apps/nexus/`. The parent `.abi/AGENTS.md` covers broader ABI conventions (hexagonal architecture, `uv` toolchain, service map). This file explains **why** NEXUS makes the choices it does, and what is NEXUS-specific.

## What NEXUS is and why it exists here

NEXUS is a multi-tenant agent platform: FastAPI backend, Next.js frontend, PostgreSQL, Cloudflare Pages for the web app, Docker for local Postgres. The same codebase must run **standalone** (its own dev loop) and **mounted** inside the parent `naas-abi` package. That dual execution model drives most of the import, Makefile, and deployment conventions below.

## Setup and commands

NEXUS ships its own Makefile because it is a vendored app with a different dev loop than the parent ABI stack (turbo api+web, local Postgres, pnpm). Running parent-repo commands from the workspace root will miss NEXUS-specific targets.

**Run from `apps/nexus/`, not from the workspace root.**

```bash
make install        # pnpm install + (cd apps/api && uv sync)
make db-up          # docker compose up -d postgres
make db-migrate     # runs init_db(); applies all apps/api/migrations/*.sql idempotently
make up             # kill-ports → ensure postgres → ./dev.sh (turbo runs api + web)
make api            # API server only
make web            # web server only
make kill-ports     # frees 3000 (web) and 8000 (api)
make check          # lint + typecheck + test
make test-watch     # pytest --lf -x in apps/api/
make db-reset       # DESTRUCTIVE: docker compose down -v, then up + migrate + seed
```

Run a single backend test:

```bash
cd apps/api && uv run pytest tests/test_auth.py::test_login_succeeds -v
```

Type-check or lint a specific area:

```bash
cd apps/api && uv run mypy app/services/chat
cd apps/api && uv run ruff check app/services/chat
cd apps/web && pnpm typecheck
```

## Python imports and dual execution modes

The same Python modules load whether you start NEXUS alone or mount it into naas-abi. Short imports like `from app.core.config import settings` only resolve when the process cwd and `PYTHONPATH` happen to include `apps/api/`. Fully qualified imports resolve in **both** modes, which is why every file under `apps/api/app/` uses the long form. Match it.

```python
from naas_abi.apps.nexus.apps.api.app.core.config import settings
```

Do not use `from app.core.config import settings`.

The standalone dev entrypoint is `apps/api/app/main.py` (`uvicorn app.main:app`, port 8000 via Makefile; port 9879 if run as `__main__`). When mounted into the parent naas-abi FastAPI app, `create_app(existing_app)` patches the parent in place rather than creating a new one.

## Backend architecture (hexagonal)

Business logic lives in `apps/api/app/services/<domain>/` using ports and adapters so domain code stays testable and infrastructure can be swapped (Postgres today, something else tomorrow) without rewriting services. The HTTP layer, streaming quirks, and SQL belong in adapters; the service layer depends only on port interfaces.

Each domain follows:

```
services/<domain>/
  port.py                                      # Abstract IxxxPort interfaces + DTOs (dataclasses)
  service.py                                   # Domain logic, depends only on ports
  handlers/<domain>__http_handler.py           # Wires service + adapters + FastAPI router
  adapters/
    primary/<domain>__primary_adapter__FastAPI.py   # HTTP request/response mapping
    secondary/postgres.py                            # DB adapter implementing the port
```

**Why double-underscore adapter names** (`<domain>__primary_adapter__<Tech>.py`): several adapters for the same domain often sit in one folder. The pattern disambiguates them at a glance and keeps filenames stable when you add a second primary adapter (for example `<domain>__primary_adapter__streaming.py`, `<domain>__primary_adapter__export.py`).

**Why migration is incremental:** legacy endpoint files in `apps/api/app/api/endpoints/` (`abi.py`, `admin.py`, `graph.py`, `secrets.py`, `view.py`, and others) still work in production. A big-bang refactor would block shipping. See `apps/api/app/services/HEXAGONAL_MIGRATION_TASKS.md`. `api/router.py` shows which domains have moved to `services/<domain>/handlers/` (chat, agents, auth, files, modules, apps, providers, workspaces) versus the ones still in `endpoints/`. When touching a legacy endpoint, check the migration doc before deciding whether to extract into a domain.

Per workspace policy: every abstract method on a port must be implemented in adapters. Raise `NotImplementedError` for genuinely unsupported features rather than omitting the method.

## Database migrations

Plain SQL files at `apps/api/migrations/NNNN_description.sql`, applied in sequential order by `init_db()` on every API startup.

**Why idempotent SQL on every boot:** NEXUS does not run a separate migration service or Alembic runner. Migrations re-apply at startup, so `IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, and similar guards are required. That trades Alembic's version table and rollback story for simpler ops in this deployment model.

**Why no Alembic:** forward-compatible SQL only. Write migrations that can run again safely.

Two non-negotiables:

1. **Idempotent**: use `IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, and similar guards. Migrations re-run on every boot.
2. **Sequential numbering**: never reuse a prefix. There is a known collision (`0016_link_workspaces_to_orgs.sql` and `0016_add_workspace_theming.sql`). Do not introduce more.

## SSE and streaming

Chat streaming receives three wire formats (OpenAI JSON-per-line, Anthropic typed W3C SSE, ABI/Naas strict multi-line W3C SSE). Each provider encodes tokens, tool calls, and errors differently.

**Why normalize to `StreamEvent`:** the domain service should not branch on OpenAI vs Anthropic vs ABI wire format. Adapters in `services/chat/adapters/primary/chat__primary_adapter__streaming.py` absorb format-specific quirks; the service operates on a single event shape.

Event types: `token | thinking | tool_call | link | file | error | done`. See `docs/ESSENTIALS.md` for protocol examples.

## Multi-tenancy and IAM

Everything below `organizations` is scoped to `workspace_id`: agents, conversations, secrets, graph nodes, inference servers.

**Why `workspace_id` everywhere:** multi-tenant isolation is a security invariant, not optional filtering. New tables and endpoints must filter by `workspace_id` and declare the action a route performs (`services/iam/`, see its `AGENTS.md`): IAM decides, memberships are its role attachments.

Do not add a role check at the endpoint: declare the action (`guard`, `declares`) and let IAM decide.

Where each part of the permission system lives (read the one you touch):

| Scope | AGENTS.md |
|---|---|
| Nexus authorization on IAM: the `nexus` catalog, roles, features, memberships, placements | `apps/api/app/services/iam/AGENTS.md` |
| Sign-in, sessions, CSRF, credential kinds, API keys, links, the old login's accounts | `apps/api/app/services/oidc/AGENTS.md` |
| The IAM admin pages (policies, attachments, groups, service accounts, approvals, simulator, audit) | `apps/api/app/services/iam_admin/AGENTS.md` |
| View as another person, read-only, in one workspace (the view on the server) | `apps/api/app/services/view_as/AGENTS.md` |
| The platform's accounts: directory, platform invitations, deactivation, deletion (Platform Settings › Users) | `apps/api/app/services/accounts/AGENTS.md` |
| Invitations and IdP group bindings | `apps/api/app/services/invites/AGENTS.md` |
| Graph access (placements and shared graphs as IAM policies) | `apps/api/app/services/graph/AGENTS.md` |
| The built-in identity provider and its trusted `/idp` route | `libs/naas-abi-idp/AGENTS.md` |

### Sign-in through identity providers

Nexus has **no login of its own**: no password, magic link, one-time code, reset, signup or refresh
token, and no token signed with `secret_key`. People sign in at an OIDC identity provider the engine
trusts (`identity.providers`; the built-in one, `libs/naas-abi-idp`, is the default), and Nexus is its
relying party. Read `apps/api/app/services/oidc/AGENTS.md` before touching it: sign-in (PKCE, the
engine redeems the code), one Nexus `users` row per `(issuer, sub)` whose id is the IAM principal id,
the `nexus_session` cookie and its CSRF token, what a cookie never authenticates (pages, frames), the
link of the old login's accounts at their first sign-in (`abi user migrate`), and the key of workspace
secrets (`secrets_encryption_key`, `NEXUS_SECRETS_KEY`).

- `services/auth/` keeps the signed-in user's account (`GET|PATCH /api/auth/me`, the avatar) and
  `credentials.py`; `services/oidc/` is the sign-in and the session.
- The web app holds the cookie session only and keeps no token (`stores/auth.ts`): use `authFetch`, or
  `withAuth` / `getAuthHeader(method)` + `authCredentials()` for a raw `fetch`, and `selectSession` /
  `hasSession` to know whether someone is signed in.
- A route that serves user bytes sends `user_content_headers` (`core/user_content.py`): user content
  never runs on the API origin, which holds the cookie.

### Credentials: which kind goes where

Every credential has a kind (its audience) and Nexus honours it only where it belongs
(`services/auth/credentials.py`, `accepted_kinds(path)`): a **session** (the cookie, or an `abi:session`
token the engine issued) everywhere and on the WebSocket; a **personal API key** (`abi_pk_...`) on `/api/*`
except the session-only prefixes `/api/auth/` and `/api/iam/`; a **coding environment's key** at the OpenAI
gateway (`/api/v1/*`) alone. App links, previews and remote-app grants are IAM grants (`abi_gk_...`, eight
hours, revocable) that open their own routes and are never sessions. The table, the key rules and the
delegations Nexus makes over NATS for the signed-in user are in
`apps/api/app/services/oidc/AGENTS.md` ("Credentials: which kind goes where"). Personal API keys:
`services/api_keys/` (`/api/iam/api-keys`, session-only; the page is `app/account/api-keys`).

### Business workspace vs Code workspace

These are distinct mental models. Do not conflate them in UI copy.

| | **Business workspace** | **Code workspace** |
|---|---|---|
| Audience | Analysts, managers, operators | Engineers |
| Role | Collaboration, reporting, assets, workflows | SCM, multi-repo, env, debugging |
| Lifetime | Long-lived | Often ephemeral |
| Auth / access | Org RBAC | Repo tokens / SSH; tied to branches, folders, containers |

Footer labels must say **Business workspace** and **Code workspace**. Canonical UX note: parent-app `docs/ux/business-vs-code-workspace.md` (or equivalent).

### Platform status footer

`WorkspaceLayout` always mounts `apps/web/src/components/shell/platform-status-footer.tsx` (desktop + mobile): **User / Business workspace / Repo / Branch / Code workspace** (+ **Saved** / **Unsaved changes** when relevant) on the left; **Refresh + API** on the right. Code workspace label links to the Coder dashboard URL from runtime binding (`https://coder…/@owner/name`) when available. Navbar must not show a fake branch selector or duplicate API chip. Slides registers Refresh via `SlidesStatusBar` (null render; no second footer) and publishes `deckDirty` / `coderUiUrl` through `stores/slides.ts`. Code syncs repo/branch/Coder through `stores/code.ts` and `stores/platform-status.ts`.

## Frontend

Next.js 14 App Router under `apps/web/`. State is Zustand (`src/stores/*.ts`, one store per domain: `auth`, `workspace`, `agents`, and others).

**Why `/api/tenant` at SSR:** tenant branding (tab title, OG image, theme) must be correct before first paint. `layout.tsx` fetches branding server-side. Do not bypass this API; it returns safe defaults on failure so white-label tenants never render a broken unbranded shell.

Cloudflare Pages deploy: `pnpm build:cf` then `wrangler pages deploy` (see `apps/web/package.json`, `wrangler.toml`). Standard `pnpm dev` runs Next.js on port 3000.

### Server routes that fetch for a page

`/api/image-data`, `/api/link-preview` and `/api/maps/*` run on the web host, which never sees the API's
session cookie. They answer only a browser that holds a **web pass** (`lib/web-pass.ts`: the auth store asks
the API for one once the session is known, renews it while the app is open and drops it when the session ends; see
`api/app/services/oidc/AGENTS.md`, "The web pass"). The readable cookie `nexus-web-pass-until` says when
the pass ends; the workspace layout renders its pages once a pass is in hand (`useWebPassReady`, five
seconds at most), so their first requests to these routes carry it. A URL a page gives them is fetched with
`lib/public-fetch.ts`: `https` on the default port, every address of every hop on the public internet (no
loopback, private, link-local or Docker network address), the connection made to the address that was
checked, three redirects, a size and a time cap. `/api/image-data` serves remote answers only as raster
images, and every image with `nosniff` and a sandboxing CSP. A logo the API serves is read from the API
with the session (`lib/logo-data-uri.ts`), never through these routes.

### View as (the web side)

An administrator sees Nexus as another person, read-only, in one workspace (server: `apps/api/app/services/view_as/AGENTS.md`). The web starts and stops the view, shows who is viewed, and keeps nothing of it. It decides nothing: IAM and the server do.

- **Start.** The person's page (`components/access/people/person.tsx`, under Platform Settings › Users and each level's Members) shows "View as <name>" (`view-as-control.tsx`) when `GET /api/iam/view-as/workspaces?principal_id=` is not empty, then a picker of those workspaces (the page's own preselected). Start posts (`lib/view-as.ts`, `beginView`), raises the flag below and loads `/workspace/<id>` (a full load: `navigation.go`, a seam for tests).
- **The view state** is `useAuthStore().view` (from `GET /api/auth/oidc/session`, `view`: person, workspace, `ends_at`, `groups_from`). During a view `user` is **the person** (read from `GET /api/auth/me`, which the server answers as them), so the dock profile, Account settings and every "me" check show them; `viewer` is the signed-in admin and the session (CSRF) stays theirs. `provider` is the session's identity provider, named by the banner when `groups_from` is null.
- **The banner** (`components/view-as/view-banner.tsx`) is in the root layout, so it covers the workspace, settings and account shells: "Viewing as <name> (read-only) in <workspace> · <n> min left · Stop", plus "without <provider> groups" when `groups_from` is null. At `ends_at` the banner reads `/session` and reloads only when the server says the view is over (retrying every few seconds otherwise: the browser's clock may be ahead of the server's, and a reload while the view still runs would loop); Stop (`endView`) deletes the view, clears the flag and loads the page the view was started from. The shells are as tall as the window, so they take `--view-banner-height` off their height (`html[data-view-as]`, set by the guard script below).
- **Nothing is kept.** The browser's hint that a view runs is the cookie `nexus-view-as` (`lib/view-flag.ts`: the viewed workspace and the page to return to, nothing of the person; it outlives the view by a margin, `FLAG_MARGIN_SECONDS`, so a browser clock ahead of the server's never drops it while the view runs; `/session` and Stop clear it). The stores and the edge middleware read it before the first request is answered, which is why it is a cookie: `lib/view-storage-guard.ts` (inlined in the root layout's head) puts in-memory storage in place of `localStorage` and `sessionStorage` for the page load, `createDeferredStorage` (every persisted store) and `getSafeStorage` (the auth store) neither read nor write, `middleware.ts` does not set `nexus-last-workspace` and lands `/` in the viewed workspace, and the WebSocket is not opened. Starting and stopping reload the browser, so nothing in memory survives. The server stays the authority: a `/session` that disagrees with the flag (another tab, cleared cookies, a view that ended) sets or clears the flag and reloads once.
- **Refusals.** A 403 whose `detail` starts with "Read-only:" or "Outside this view:" is the view's: `authFetch` shows it as a toast (`onViewRefusal`, hosted by the banner), does not re-read the session for it, and leaves the response to the caller.
- **Private pages** say "Private to <name>" and fetch nothing (`components/view-as/private-to-person.tsx`, `PrivateGate`): the workspace's secrets, the account's API keys, coding environments, My Files (the files store, the explorer tree and the browse page; `GET /api/files/views` does not list it in a view) and chat history (the conversation sync, the chat search and the sidebar list).
- **Decision: a cookie, not a store, says a view runs before anything loads.** Consequences: the flag can be stale (fail-safe: nothing is persisted for a few minutes, the server's answer wins); a new store that persists must go through `createDeferredStorage` or `getSafeStorage`, or it is covered by the guard script only.
- **Decision: the person replaces the viewer in the store, not beside it.** Consequences: no component needs to know about views to show the person; a component that must act as the viewer (Stop, sign-out) reads `viewer` or uses the session as it is.
- Tests: `lib/view-flag.test.ts` (flag, guard script, storages, middleware), `stores/auth-view.test.ts`, `components/view-as/*.test.ts`, `components/access/people/{person,view-as-control}.test.ts`, `contexts/websocket-context.test.ts`.

## Web styling conventions

This is the most opinionated area of the frontend. The choices below exist because NEXUS is a **tenant-branded product UI**, not a single-theme internal tool.

### Why semantic CSS for product surfaces

Our approach is informed by [Tailwind CSS vs Semantic CSS](https://dev.to/7jw92nvd1klaq1/tailwindcss-vs-semantic-css-411j). That article's core tradeoff: Tailwind wins on prototyping speed; semantic CSS wins on readable markup and explicit control over design.

We hit the semantic side of that tradeoff in practice. Utility-class strings scaled poorly across account settings, org settings, and shell regions: brand colors drifted (blue vs green), org border radius was applied inconsistently, and refactors required grep-heavy string surgery instead of editing one CSS rule. Semantic class names plus co-located stylesheets give reviewable JSX and a single place to enforce tenant tokens.

What we add beyond that article: design tokens in `globals.css`, org `--org-border-radius` propagation, route file conventions, and commit granularity for upstream cherry-picks. That is a production design system, not bootcamp vanilla CSS.

### Why hybrid (Tailwind shell + semantic pages)

Full Tailwind removal would block shipping. The app shell and layout scaffolding change less often and benefit from Tailwind's speed during migration. Product surfaces where brand consistency matters use semantic CSS with co-located stylesheets. Migrate route by route; do not wait for a monolithic rewrite.

### Why the route file convention

Each migrated route uses three files so structure, routing, and style stay separable:

```
{segment}/page.tsx   → export { default } from './{segment}';
{segment}.tsx        → component implementation
{segment}.css        → semantic styles, imported in the tsx file
```

Example: `src/app/account/api-keys/page.tsx` re-exports from `./api-keys`, which imports `./api-keys.css`.

This yields reviewable diffs, cherry-pick friendly commits to upstream ABI (product integration branches unpack into small PRs to jupyter-naas/abi main), and clear ownership: routing vs component vs CSS.

### Why `{surface}-{region}-{element}` class names

Kebab-case with the pattern `{surface}-{region}-{element}[-{modifier}]` avoids collisions across account pages, shell chrome, and org settings. Names are grep-friendly and self-documenting in JSX.

Examples:

- `account-api-keys-page`
- `account-api-keys-table-row`
- `shell-sidebar-list-row`

The shell uses the same convention via `src/components/shell/tokens.ts`, which exports class name strings for JSX while styles live in `globals.css`.

### Why design tokens in `globals.css`

Tokens are the single source for brand green, spacing scale, typography, and org radius. Page CSS reads them with `var(...)`. Org-specific `--org-border-radius` must propagate to portals and nested layouts (see `src/app/account/layout.tsx` and `src/components/shell/workspace-layout.tsx`).

Page-level semantic CSS reads tokens from `apps/web/src/app/globals.css`:

- Colors: `--color-primary`, `--color-primary-hover`, `--color-primary-focus`, `--foreground-hex`, and related hex tokens
- Spacing: `--space-1` through `--space-12`
- Typography: `--font-size-*`, `--line-height-*`, `--font-weight-*`
- Org radius: `--org-border-radius`

Rules for page CSS:

- Use hex colors, not `rgba()`
- Use `px`, not `rem`, for page-level semantic CSS
- Reference tokens with `var(...)`. Do not hardcode brand colors such as `#3B82F6`
- Do not use `@apply`. Write plain CSS selectors

**Why hex and px:** predictable rendering across tenants; no rem cascade surprises; matches design handoff specs.

### Org branding

Org-specific border radius comes from the org `loginBorderRadius` field and is exposed as `--org-border-radius`. The tenant's `login_border_radius` is applied first on `document.documentElement` (`data-org-branded` and `--org-border-radius`) so pages outside the workspace shell follow it; a workspace then overwrites `--org-border-radius` with its organization's value. Layouts also set `data-org-branded="true"` on the branded subtree. Avatars always use `9999px` border radius and are excluded from org radius overrides.

In semantic CSS, prefer:

```css
border-radius: var(--org-border-radius, 0px);
```

### Pilot references

Use these as templates when migrating routes:

- `apps/web/src/app/account/api-keys/` (page, component, css)
- `apps/web/src/app/globals.css` (design tokens and org branding rules)
- `src/components/shell/tokens.ts` (class name exports for shell)

### Why tiny commits per route

When migrating routes from Tailwind to semantic CSS, keep commits small and focused per route. Small commits integrate cleanly when unpacking branch work into upstream ABI PRs.

## Account UI module

The account settings surface is a self-contained module under `apps/web/src/app/account/`. It uses semantic CSS throughout: layout shell, shared components, and per-route styles. No Tailwind in layout or route TSX files.

### Structure

```
src/app/account/
├── layout.tsx                 # Shell: header, sidebar nav, org branding
├── account-layout.css         # Layout semantic styles + responsive rules (zero Tailwind)
├── lib/
│   └── nav.ts                 # accountSettingsNav + AccountSettingsNavItem type
├── components/
│   ├── account-components.css # Shared component styles
│   ├── account-page-header.tsx
│   ├── account-section-card.tsx
│   ├── account-toggle.tsx
│   └── account-action-row.tsx
├── profile/                   # page.tsx + profile.tsx + profile.css
├── appearance/
├── api-keys/
├── security/
└── notifications/
```

### Shared components

| Component | Purpose | Used by |
|---|---|---|
| `AccountPageHeader` | Title + subtitle; optional `actions` slot | All 5 routes |
| `AccountSectionCard` | Bordered card shell (`padded`, `stack`, `flush`, `overflowHidden`) | profile, api-keys, security, notifications |
| `AccountToggle` | Pill on/off toggle | notifications |
| `AccountActionRow` | Icon + title + description + action button | security |

Navigation config lives in `lib/nav.ts` and is imported by `layout.tsx`.

### Responsive layout

Mobile breakpoints live in `account-layout.css` (and route CSS where needed), not in `layout.tsx`. Below 768px (same threshold as `useIsMobile()` / Tailwind `md`), the sidebar becomes a horizontal scroll nav strip above full-width content. Shared components and route pages add their own `@media (max-width: 767px)` rules for stacked headers, action rows, tables, and forms.

### Route convention (unchanged)

Each route keeps three files:

```
{segment}/page.tsx   → export { default } from './{segment}';
{segment}.tsx        → route component (imports shared components + segment.css)
{segment}.css        → route-specific semantic styles only
```

Route CSS holds page-specific layout and elements not covered by shared components. Shared patterns (headers, cards, toggles, action rows) belong in `components/account-components.css`.

Pilot reference for a fully migrated route: `apps/web/src/app/account/api-keys/`.

## Workspace settings

`/workspace/<id>/settings/...` (`apps/web/src/app/workspace/[workspaceId]/settings/`): what the workspace has and its configuration. Nothing is added to a workspace, and nothing is turned on or off, here: who may use what is on Access › Policies.

- **Who opens them** (UJ-W1), the one rule of the dock's Settings, the mobile More sheet, quick open and every settings page (`hooks/use-workspace-settings-access.ts`, `workspaceSettingsAccess` and `settingsPageOpens` in `settings-nav.tsx`): `all` when the caller's role in the workspace brings the settings (`settings.workspace`: its owners and admins), `iam` when it does not but IAM shows them a page of Access there (`GET /api/iam/admin/access?scope=<workspace container>`: those pages and a member's page alone; any other settings page, and `/settings`, send them to the first they hold, `settingsLandingPath`), `none` otherwise: every settings page, opened by URL, says "You have no access to these settings" instead of rendering. Nothing is shown until the access is read. The workspace layout's feature guard leaves settings paths to this rule (`getGatingFeatureForWorkspacePath` answers null for them). Tests: `settings-nav.test.ts`, `settings/layout.test.ts`.
- **Sidebar** (`components/shell/settings-nav.tsx`, `SETTINGS_GROUPS`): General (General, Members, Secrets, Data Export) and Features (Agents, Apps, Graphs, Maps, Models, Ontologies, Search, Skills, Workflows). A Features entry names the Nexus `feature` it manages and the module resources it lists (`kinds`); `visibleSettingsGroups` keeps those the caller may use in the workspace (`settingsItemShown`, pure, tested in `settings-nav.test.ts`). Apps needs the `apps` feature and an app the caller may open, Workflows a workflow or a pipeline the caller may run, Agents the `agents` feature only (agents the workspace builds need no module), Models no feature. What the caller may use comes from `GET /api/workspaces/{id}/resources` (`hooks/use-workspace-resources.ts`: the enabled features the caller holds, IAM `UseFeature`, and each module with the agents, apps, workflows and pipelines IAM lets the caller use), read again each time the settings open and on Reload; a failed read is never kept (the last answer stays). Until it answers, or for a caller who may not read it, the caller's own feature flags decide the features and module resources are assumed; so are the kinds the API names `unavailable` (discovery or the jobs did not answer), so a short count never hides a page or gates it. A page of an entry the caller may not use (`settingsItemFor`) shows `not-in-workspace.tsx` instead.
- **Agents, Apps, Workflows** list exactly the agents, apps, workflows and pipelines the caller may use in the workspace and it offers (IAM's `module:UseAgent`, `OpenApp`, `RunWorkflow` / `RunPipeline`, then the workspace's offer, through `authz.filter_scopes`): `GET /api/agents`, `GET /api/apps/?workspace_id=`, `GET /api/workspaces/{ws}/workflows/settings` (`workflows/workflows-model.ts`, tested in `workflows.test.ts`). There is no on/off switch: the old flags (`agent_configs.enabled`, `app_configs.enabled`, `workflow_visibility`) are read by nothing. Agents keeps each agent's configuration (name, prompt, model, the default, `PATCH /api/agents/{id}`), and the agents a workspace builds itself (a model and a prompt) are still created and edited there; one is listed and used by who holds `nexus:UseAgent` on it (one turned off before the upgrade is denied there).
- **General** shows read-only what the caller may use here: the deployment's enabled features (`/configuration`) and each module with what the caller may use of it (`/resources`, `describeModuleResources`). Who may use what is set on Access › Policies.

Decisions:

- **Policies are the one place access is decided.** Decision: the workspace on/off toggles of Agents, Apps and Workflows are gone (with `services/visibility`); what a user lists and uses there is IAM's decision alone, the platform admin included. A workspace that should not offer a module's agent, app or workflow denies it in a policy (the upgrade turned what was turned off into Denies). Consequences: no workspace settings page switches anything; the routes that only toggled are removed (`/api/apps/{ws}[/{app_id}]`, `PUT /api/workspaces/{ws}/workflows/settings`), `enabled` is no field of an app or an agent; the `nexus` actions those routes asked (`GetApp`, `InstallApp`, `UpdateApp`, `UninstallApp`, `UpdateWorkflow`) stay declared, deprecated, so a policy naming them never blocks the catalog's registration.

## Organization settings UI module

Organization **admin** settings (not the tenant portal at `/org/[orgSlug]`) live under `apps/web/src/app/organizations/`. The org picker stays at `/organizations`. Per-org settings are a self-contained module at `organizations/[orgId]/settings/`, structured like Account: semantic layout shell, shared components, route parser, and per-section `{segment}.tsx` + `{segment}.css`.

### Structure

```
src/app/organizations/
├── page.tsx                              # Org picker (multi-org); single-org redirects into settings
├── layout.tsx                            # Pass-through
└── [orgId]/settings/
    ├── layout.tsx                        # Shell: header, sidebar nav, org branding, mobile list-detail
    ├── org-settings-layout.css           # Layout semantic styles + responsive rules
    ├── page.tsx                          # Desktop → general; mobile list via layout
    ├── lib/
    │   ├── nav.ts                        # orgSettingsNav + path helpers
    │   ├── org-settings-route.ts         # parseOrgSettingsRoute (mobile list-detail)
    │   └── org-settings-route.test.ts
    ├── components/
    │   ├── org-settings-components.css
    │   ├── org-settings-page-header.tsx
    │   └── org-settings-section-card.tsx
    ├── general/                          # page.tsx + general.tsx + general.css (pilot)
    ├── workspaces/                       # list (links each workspace to its modules column), new/ (create)
    ├── policies/, groups/                # Access › Policies and Groups (components/org-access.tsx): the shared UI at the org and its workspaces
    ├── branding/
    ├── users/                            # people access (Admin is a role, not the section)
    ├── domains/
    └── billing/
```

Do **not** merge this surface with `/org/[orgSlug]` (tenant login / workspace portal). Different product paths.

### Shared components

| Component | Purpose | Used by |
|---|---|---|
| `OrgSettingsPageHeader` | Title + subtitle; optional `actions` slot | All settings sections |
| `OrgSettingsSectionCard` | Bordered card shell (`padded`, `stack`, `flush`, `overflowHidden`) | general, users, domains |

Navigation config lives in `lib/nav.ts` and is imported by `layout.tsx`. Path helpers: `orgSettingsIndexPath`, `orgSettingsSectionPath`.

Organization settings open for the caller (their tab, `/organizations`) exactly when IAM would open a section for them in one of their organizations (`hooks/use-organization-settings-access.ts`, `opensOrganization` for one, `opensOrganizationSettings` for the list): their role there is owner or admin, or `GET /api/iam/admin/access?scope=<org container>` opens a page of its Access (`opensAccess(access, 'organization')`). `GET /api/organizations` carries `current_user_role` for each organization (IAM's roles, read once), so the roles come in one answer; the access is read only for the organizations where the role is no admin's, `ACCESS_BATCH` (8) at a time, every organization counted, stopping at the first batch that opens one. One request per user is shared, a failure keeps the last answer, and nothing is shown while checking. Never from a workspace role: a workspace owner who is only a member of the organization does not see it (UJ-O1).

**By URL, the same rule.** The settings layout decides with `orgSettingsAccess` (`lib/nav.ts`): `admin` (its owners and admins: every section), `iam` (the pages of Access IAM opens to them, and a member's page from a policy's holders, nothing else: any other section sends them to the first they hold, `orgSectionRedirect`), `none` (no section at all: every page, the phone index included, says "You have no access to these settings", `components/settings/settings-no-access.tsx`), `unknown` until the organization (its role) and, for a non-admin, the access were read (nothing is shown). A member of the organization (Eve) no longer sees General or Workspaces there. `/organizations` lists, and goes straight into when there is one, only the organizations that open for the caller (`openableOrganizations`).

### Responsive layout

Mobile breakpoints live in `org-settings-layout.css` (same 768px threshold as `useIsMobile()`). Below 768px:

- `/organizations/[orgId]/settings` = settings section list (nav only)
- `/organizations/[orgId]/settings/{section}` = immersive detail (header title = section label; back returns to list)

Desktop keeps sidebar nav + content. Index redirects to `/settings/general`. Safe-area insets and `var(--org-border-radius, 0px)` apply on the shell; mobile nav labels use `--font-size-xs` (12px).

### Route convention

```
{segment}/page.tsx   → export { default } from './{segment}';
{segment}.tsx        → route component
{segment}.css        → route-specific semantic styles
```

Pilot (full semantic CSS): `general/`. Other sections use the three-file layout and shared header; branding/billing/workspaces may still carry Tailwind in the section body until a later pass.

### Users admin capability (shared API)

Org **Users** and workspace **Members** are UI channels over the same Nexus HTTP admin APIs used by `abi user invite` / `abi workspace members add` / `abi org members` (CLI). Do **not** reimplement invite business logic in React; call these endpoints via `authFetch` / `useOrganizationStore`.

| Action | Endpoint | Who |
|---|---|---|
| List org users | `GET /api/organizations/{orgId}/members` | Org member |
| Add org user (create-on-invite) | `POST /api/organizations/{orgId}/members/invite` `{email, role, name?, workspace_id?, workspace_role?}` | Org owner/admin |
| Update / remove org user | `PATCH` / `DELETE` `/api/organizations/{orgId}/members/{userId}` | Org owner/admin |
| Remove from organization (every workspace of the org and any org role, in one step) | `DELETE /api/organizations/{orgId}/members/{userId}/access` | Org owner/admin (`RemoveOrganizationMember`) |
| List workspace members | `GET /api/workspaces/{id}/members` | Workspace member |
| Invite workspace member (create-on-invite) | `POST /api/workspaces/{id}/members/invite` `{email, role, name?}` | Workspace owner/admin |

Notes:

- Invite of an email with **no account** goes through an identity provider (`services/invites`): the provider makes the person, IAM holds the roles, the first sign-in claims them; with no provider configured it answers 400. Someone who **already has an account** is added directly and told by an email with a sign-in link (no code: the provider mails it). Optional `workspace_id` on org invite also adds workspace membership.
- UI must hide or disable Add / Invite for non-admins; API still returns `403`.
- **Remove from organization** (Org settings › Users, the row's remove button and the user's page): someone with workspace access only (no org role) leaves every workspace of the organization in one step (`DELETE …/members/{userId}/access`, `OrganizationService.remove_from_organization`); their platform account stays, with what they hold in other organizations. A member with an org role loses the org role (`DELETE …/members/{userId}`) and keeps their workspace access, so the list is read again after a removal. An org owner is never removed this way (400: demoted first by an owner, so the last owner never leaves), nor oneself; a workspace's last owner is a 409 that names the workspace. Every change is checked by IAM before the first is made, so a refusal changes nothing. The confirm dialog says what is taken and what stays (`removalConfirmation`, `users-model.ts`).
- **Agents:** `invite_organization_member` / `invite_workspace_member` in `naas_abi/tools/nexus_admin_tools.py` use the same create-on-invite path in-process.

Web entry points: `organizations/[orgId]/settings/users/`, workspace `organization/users/`, workspace `settings/users/` (once Members: `/settings/members[/...]` redirects there). Store: `stores/organization.ts`.

A role change, on these pages as on a person's page, is `changeMemberRole` (`components/access/roles/role-change.ts`): the membership route of its level, the roles a page may give (`assignableRoles`) and the ones it never changes (`roleChangeable`: an owner's, one inherited from the organization, one's own). The pages keep invitations.

## Maps UI module

Maps is a **dataset loader**, not the Knowledge Graph. Graph stays under `/graph` (ontology network). Maps sits first in the primary nav (before Search) and loads datasets onto a canvas.

**Ownership rule:** Nexus Maps owns situation-awareness Public layers as first-class product code under `apps/web/src/app/workspace/[workspaceId]/maps/` plus Maps API proxies under `apps/web/src/app/api/maps/`. Do **not** import from `naas_abi_marketplace/.../wsr`. World Situation Room is a legacy marketplace demo; do not couple Maps to it.

The Maps sidebar mirrors Search sources: collapsible **Public / Private / Custom** groups with `active/total` counts, icon + label rows, and `org-border-radius` via `maps-*` CSS. Empty buckets (including Custom upstream) are hidden. Maps in ABI is generic: product-specific datasets (for example a parent-app World Organization Graph) are registered by the deployment through the Custom bucket contract below, never hard-coded into upstream ABI.

| Bucket | Dataset | Route | Role |
|---|---|---|---|
| Public | OpenStreetMap | `/maps/openstreetmap` | Standard OpenStreetMap basemap |
| Public | Earthquakes | `/maps/earthquakes` | USGS M≥2.5 past-day GeoJSON |
| Public | Wildfires | `/maps/wildfires` | EONET named fires (7d); optional FIRMS VIIRS WMS when `FIRMS_MAP_KEY` set |
| Public | Temperature | `/maps/temperature` | Open-Meteo current 2m air temp city samples |
| Public | Natural Earth | `/maps/natural-earth` | NE 110m country borders GeoJSON |
| Public | GDACS | `/maps/gdacs` | UN GDACS multi-hazard events (`/api/maps/gdacs`) |
| Public | EONET Events | `/maps/eonet-all` | NASA EONET all open events (30d); wildfires stay separate |
| Public | Air Quality | `/maps/openaq` | OpenAQ when keyed; else Open-Meteo PM2.5 samples |
| Public | NWS Alerts | `/maps/nws-alerts` | US NWS active alerts via `/api/maps/nws` (User-Agent) |
| Public | Tropical Storms | `/maps/tropical-storms` | NHC CurrentStorms via `/api/maps/nhc` |
| Public | Volcanoes | `/maps/volcanoes` | NASA EONET volcano category (90d) |
| Public | Flights | `/maps/flights` | Viewport adsb.lol (zoom 4+); global airplanes.live sample when zoomed out (`/api/maps/flights`) |
| Public | Conflict Sites | `/maps/conflict` | Curated static OSINT pins in `maps/lib/conflict-sites.ts` |
| Public | Gulf Strikes | `/maps/gulf-strikes` | Live Gulf / Iran / Israel strike RSS geopins via `/api/maps/gulf-strikes` |
| Public | News | `/maps/news` | RSS proxy → light region geocode pins |
| Public | AIS Vessels | `/maps/ais` | AISStream snapshot when `AISSTREAM_API_KEY` is set on nexus-web; honest empty state otherwise |
| Public | ISS | `/maps/iss` | open-notify ISS position (bonus thin orbit pin) |
| Private | **Here** (presence) | `/maps/presence` | User map: laptop / this device, optional iPhone pin, GCP `abi-naas-app` |
| Custom | *(empty upstream)* | `/maps/{id}` | Registered per deployment via `NEXT_PUBLIC_MAPS_CUSTOM_DATASETS`; do not ship product-specific datasets here |

**Custom bucket contract.** Upstream ABI ships the mechanism, never a particular layer. A deployment registers its own by setting `NEXT_PUBLIC_MAPS_CUSTOM_DATASETS` to a JSON array of descriptors (`src/lib/maps-custom-datasets.ts`), so a Custom layer only appears where an operator has pointed it at a backend that exists:

```json
[{ "id": "acme-sites", "title": "Acme Sites", "description": "Sites Acme operates.",
   "icon": "MapPin", "order": 0, "endpoint": "/api/acme/sites" }]
```

Every environment-registered layer renders through `MapsCustomFeed` and fetches through the authed proxy at `/api/maps/custom/[datasetId]`, which requires a Bearer token plus `workspace_id` and is never cached. `endpoint` must be a **path on the Nexus API**: the proxy forwards the caller's token, so absolute and protocol-relative URLs are rejected at parse time, as are ids that are not route-safe and ids that shadow a built-in dataset.

**Runtime graph layers.** Modules may instead call `register_map_layer(app, GraphMapLayer(...))` from their FastAPI hook. `GET /api/maps/layers?workspace_id=...` discovers only layers whose declared graph is readable. `/api/maps/layers/{id}` checks authentication, workspace membership and graph grants, then supplies a scoped store to the module projection. The browser loads these Custom layers through `MapsGraphFeed` without deployment-specific frontend configuration. Optional pin metadata (`entityUri`, `graphUri`, `country`, `precision`, `observedAt`, `sources`, `relationships`, `address`, `photoUrl`, `streetViewUrl`, `imageSearchUrl`) enables search, country filtering, the KG inspector, cited photos and constructed Street View / image-search links. The pin inspector is a place card: photo strip, title, action chips, then address. Cited `foaf:depiction` HTTPS URLs are included when present. `/api/maps/place` returns Google Place Photos and Details when `GOOGLE_PLACES_API_KEY` or `GOOGLE_MAPS_API_KEY` is set on nexus-web. Without a key, the first photo is Street View Static via `/api/maps/streetview` (OSM preview if that API is also keyless). Do not scrape Google Images or ship keys as `NEXT_PUBLIC_*` or `VITE_*`. Street View and Directions use lat/lng via the Google Maps URLs API; do not hardcode Place FIDs. Never substitute a local ledger when the live graph is empty. See `services/maps/AGENTS.md`.

A graph feed can supply optional `coverage: {pins: [...]}` alongside address `pins`. Coverage pins carry the same evidence metadata plus `memberIds` referencing address IDs in the same feed. This enables an Addresses / City coverage switch on the same Leaflet map. Natural Earth provides geographic boundaries only; city counts, country presence and drill-down membership come from the authorized module projection. Country fills support mouse and keyboard selection. Boundary-fetch failures leave city markers usable. No product-specific country lists or graph queries belong in ABI.

Graph-layer evidence panels start closed, open from the Locations toolbar button or a marker, and float over the canvas at a compact width. Do not reserve a permanent inspector column. The mobile panel occupies at most 45% of the map height and keeps attribution visible.

Basemap tiles use `https://tile.openstreetmap.org/{z}/{x}/{y}.png` directly in both themes, with visible OpenStreetMap attribution and normal browser caching/referrer behavior. No API key or tile proxy is required. Standard tile layers carry `maps-basemap`; dark-mode CSS recolors only their tile images and updates map chrome immediately when the workspace theme changes. Never apply the filter to the entire map or to thematic/WMS overlays, markers, or attribution. Do not restore unauthenticated CARTO raster URLs: they return an API-key watermark. Follow [OSM tile policy](https://operations.osmfoundation.org/policies/tiles/); do not prefetch or bulk-download tiles.

Shared Leaflet bootstrap: `maps/lib/leaflet-map.ts` + `maps-feed-canvas.tsx`. CORS / User-Agent proxies live only under `/api/maps/*` (Maps-owned). Each proxy is exported through `mapsRoute` (`api/maps/_guard.ts`): it answers signed-in users only (their web pass, `lib/web-pass-server.ts`; the middleware stops a request without one), at most `perMinute` requests a minute per user, and a proxy that spends a deployment key (Google Places and Street View, FIRMS, OpenAQ) keeps its upstream answers on the server for `cacheSeconds` (64 MB per process at most, expired answers dropped first); answers are `private`. `custom/` keeps its own Bearer check. FIRMS VIIRS WMS is proxied at `/api/maps/firms` only when `FIRMS_MAP_KEY` (or `NEXT_PUBLIC_FIRMS_MAP_KEY`) is set; without a key the Wildfires canvas is EONET-only (never ship a keyless/placeholder FIRMS WMS URL). OpenWeather temp tiles are not used (keys required). AIS is a process-local AISStream WebSocket on the Node Maps runtime (`next start` / Docker nexus-web); Cloudflare Pages isolates cannot hold the stream and must report that. Live flights and AIS pass map bounds on pan/zoom. Toolbar meta shows source, coverage, and observation age. `fetchPins` may return either a pin array or a `MapsFeedResult`.

Map initialization must receive the effect's abort signal and check it after lazy imports, before constructing Leaflet. Feed refreshes share the same setup promise; teardown owns only that effect's map and markers. Keep Strict Mode enabled. `maps/components/maps-feed-canvas.test.ts` mounts the real component and Leaflet in jsdom to cover remounts, marker selection, country filtering and stale requests after dataset changes. Run `pnpm test maps-feed-canvas.test.ts leaflet-map.test.ts maps-feed.test.ts maps-view.test.ts maps-pin-media.test.ts datasets.test.ts src/app/api/maps/ais/store.test.ts src/app/api/maps/flights/route.test.ts src/app/api/maps/streetview/route.test.ts`, then `pnpm typecheck`. Vitest and jsdom are locked local development dependencies.

```
src/app/workspace/[workspaceId]/maps/
├── page.tsx                      # Desktop → presence; mobile list via shell MapsSection
├── [datasetId]/page.tsx          # Loaded dataset canvas
├── lib/
│   ├── maps-route.ts             # parseMapsRoute, mapsDatasetPath (mobile list-detail)
│   ├── maps-route.test.ts
│   ├── datasets.ts               # Registry + Public/Private/Custom categories
│   ├── datasets.test.ts
│   ├── leaflet-tiles.ts
│   ├── leaflet-map.ts            # Shared Leaflet bootstrap / pin helpers
│   ├── maps-feed.ts              # /api/maps pin fetch + EONET parse
│   └── conflict-sites.ts         # Static OSINT conflict pins (copied data, no WSR import)
└── components/
    ├── maps-components.css
    ├── maps-section.tsx          # Sidebar + MapsDatasetGroups (Search-shaped; hides empty)
    ├── maps-library.tsx          # Same grouped list for library chrome
    ├── maps-feed-canvas.tsx      # Shared Public pin canvas
    ├── maps-openstreetmap.tsx … maps-iss.tsx
    ├── maps-gulf-strikes.tsx     # Gulf / Iran / Israel strike RSS canvas
    ├── maps-presence.tsx
    └── maps-presence-map.tsx

src/app/api/maps/                 # Maps-owned proxies (gdacs, nws, nhc, flights, gulf-strikes, news, …)
```

Sidebar expand state: `stores/maps.ts` (`nexus-maps` persist). Feature flag: `maps` (enabled by default for owner/admin/member/viewer baselines). Mobile: `/maps` = library list, `/maps/{id}` = canvas detail. Workspace nav default order is Home, Apps, Lab, Files (then Chat, Search, Maps, ...). Icons reorder by drag; Settings stays pinned. The left nav is the dock: default width matches the feature column (256px), drag the dotted handle to resize (down to icon-only). The workspace mark at the top of the dock opens the Workspaces column (search, recents, full list). The avatar at the bottom of the dock (below Settings, `DockProfile`) opens the account menu; Account opens `/account/profile`. It is session chrome, not a feature column. Desktop header does not show a user avatar. Home (`/home`) is the desktop canvas: no column. `background_image_url` on the workspace theme (module public asset, rewritten to `/modules/...`) paints the desk. When that URL is missing, the desk is `#0a0a0a`. White theme color is never the desk. The hero overlay sits on the photo only. Icons: Chat and Files when those features are on, then enabled installed apps and starred files. App landing (middleware `/`, login, workspace switch) remains Chat (`/chat`).

## Files UI module

The workspace files surface is a self-contained module under `apps/web/src/app/workspace/[workspaceId]/files/`. Mobile chrome and desktop browse chrome (toolbar, table, grid, pagination) use semantic CSS in colocated route and component styles.

### Structure

```
src/app/workspace/[workspaceId]/files/
├── page.tsx                      # Desktop browser (re-exports browse)
├── lib/
│   ├── files-route.ts            # parseFilesRoute, filesBrowsePath (mobile list-detail)
│   ├── files-route.test.ts
│   ├── drive-label.ts            # Views (sources), scopes, roots, labels, old sources, Drive/View choices, breadcrumbs
│   ├── drive-label.test.ts
│   ├── drive-settings.ts         # "Drive settings…": Platform settings › Drives, shown to holders of nexus:ListDrives
│   └── drive-settings.test.ts
├── components/
│   ├── files-components.css      # Shared chrome styles (mobile, Drive/View dropdowns, All Views)
│   ├── files-view-picker.tsx     # Drive and View pickers (sidebar; ontology picker, single choice)
│   ├── files-views-root.tsx      # All Views: one folder per view; view icons
│   ├── files-mobile-toolbar.tsx
│   ├── files-mobile-row.tsx
│   └── files-add-sheet.tsx
└── browse/                       # File browser (mobile detail + desktop)
    ├── page.tsx                  → export { default } from './browse';
    ├── browse.tsx
    └── browse.css                # Route layout + responsive visibility
```

### Shared components

| Component | Purpose | Used by |
|---|---|---|
| `FilesViewPicker` | Drive and View pickers, stacked (Drive above View): `SearchPicker` in its `single` mode | `files-section.tsx` |
| `FilesViewsRoot` | All Views: one folder per view the caller may open | `browse.tsx` |
| `FilesMobileToolbar` | Add, refresh, view mode, search (mobile) | `browse.tsx` |
| `FilesMobileRow` | OneDrive-style list row | `browse.tsx` |
| `FilesAddSheet` | Bottom sheet for create/upload actions | `browse.tsx` |

Route parsing lives in `lib/files-route.ts` and is imported by `workspace-layout.tsx` and `files-section.tsx`.

### Drives and views

One **drive**, the File System (the object storage), holds every file. The drives (the storage backends) are listed read-only in Platform Settings › Drives (`app/settings/drives`, `GET /api/platform/drives`, `nexus:ListDrives`: platform admins), with type, provider, location and whether the storage answers, never a credential; Workspace settings › Drives is gone (its URL opens Workspace settings). Files › "Drive settings…" opens that page and is shown only to holders of `nexus:ListDrives` (`lib/drive-settings.ts`, from `GET /api/iam/admin/access` through `usePlatformSettingsAccess`).

A **view** is a starting folder of a drive, under `naas_abi/`, served by the files API (`/api/files`, `?scope=`), shown to who IAM lets in. The views' sources, scopes and roots are in `lib/drive-label.ts`; a deep link is `?source=<view>&path=<path>`.

| View | Source / scope | Root | Made by | Who reaches it |
|---|---|---|---|---|
| My Files | `my-files` / `my_drive` | `my-drive/<user>` | `MyDriveWriter`, `backfill_my_drives` | the user (`my_file/<user>`) |
| Workspace Files | `workspace-files` / `workspace` | `workspace-drive/<ws>` | `WorkspaceDriveWriter`, `backfill_workspace_drives` | the workspace's roles (`ListFiles`…, `file/workspace/...`) |
| Organization Files | `organization-files` / `organization_drive` | `organization-drive/<org>` | `OrganizationDriveWriter`, `backfill_organization_drives` | decided at the organization (`ListOrgFiles`, `GetOrgFile`: viewers and up; `PutOrgFile`, `DeleteOrgFile`: admins and owners; `<org>/nexus:file/organization/...`), then its policies |
| Platform Files | `platform-files` / `platform_drive` | `platform-drive` | `backfill_platform_drive` | the people of a workspace whose offer gives it (`GivenPlatformFiles`: Off, Read, Read and write, within each person's level), or a policy at the platform (`ListPlatformFiles`, `GetPlatformFile`, `PutPlatformFile`, `DeletePlatformFile` on `abi:nexus:platform_file/platform/...`, with `object_storage:*Object*` on `abi:object_storage:object/naas_abi/platform-drive/*`); the platform admin |
| System Files | `system-files` / `system_drive` | the whole store | none | the platform admin (`ListObjectStoreFiles`, `GetObjectStoreFile`, `PutObjectStoreFile`, `DeleteObjectStoreFile` on `abi:nexus:system_file/system/...`, no role's) |

The storage paths (`my-drive/`, `workspace-drive/`…) and the API scopes keep their old names: only the views were renamed (#1530).

- **The Files page and sidebar** show the same two dropdowns, then the search (`FilesViewPicker`): **Drive** (All Drives, File System) and **View** (All Views, then the views the caller may open, in the API's order). With one drive, both Drive choices list the same views. The choices live in the files store (`activeDrive`, `chooseDrive`; `viewChoice`, `chooseView` for the View dropdown), so the page and the sidebar agree; `activeSource` is what is open: `all` or a view.
- **The dock and Home open Files on Workspace Files inside All Views** ("All Views / Workspace Files"; `openFilesEntry`, `FILES_ENTRY`), All Views itself when the caller may not open Workspace Files; a `?source=` link, a starred item or the View picker still choose their own view. A tree, starred or deep-link navigation lists its folder once its view is open (`lib/files-navigation.ts`). **The URL holds the page's state**: `?drive=&view=&source=&path=` (+ `preview=` on links). `filesNavigationFromUrl` applies a URL the page has not applied or written yet in this page load (page load, link, browser Back/Forward; a bare `/files` opens the default; folder names may contain dots, the file guess is for old `?source=&path=` links only); a URL the page wrote (Back from another page, a remount) re-uses the store, and the mount run lists the folder the store shows for the open view (`listedSource`). `filesUrlSearch` writes only a settled state (listing of the open view, not loading, no error) with `history.replaceState(null, …)`, recording it first so it never comes back as a URL to apply; other parameters such as `spacing` are kept. The source-change effect runs once per (workspace, view), so StrictMode's second mount run does not list the root over a navigation's folder.
- **All Views** (the store's default) is one folder per view the caller may open (`viewFolders`), each opening into its view: on the page `FilesViewsRoot`, then the breadcrumb `All Views / <view> / …`; in the sidebar one row per view with its tree. Nothing is asked of the files API for it (`filesScopeForSource('all')` is null: the store lists nothing and refuses to create anything there). With one view chosen, the page opens on its root and the sidebar shows its tree.
- **Which views**: `GET /api/files/views?workspace_id=` (`lib/file-views.ts`; `hooks/use-file-views.ts` shares one request per workspace between the page and the sidebar, and File › Refresh asks again). Workspace Files and Organization Files are the current workspace's and its organization's. Organization Files is labelled so, not with the organization's name, and is not listed for a workspace in no organization. A view that is open but not listed (another workspace's, a link's, a starred item's) goes back to All Views once the views are known (`useOfferedFileViews`, `offeredSource`).
- **My Files** opens on the user's folder (`documents/`, `downloads/`, `uploads/` and what they added); system files (`.manifest.json`, `.nexus_folder`) stay hidden unless View › Show system files is on. In a View-as session it is private (`PrivateToPerson`, and the store asks for nothing).
- **Old links and starred items**: `?source=my-drive|workspace|organization-drive|platform-drive|system-drive` and starred items kept in `localStorage` with those sources open the view they became (`filesSourceFrom`, used by `parseFilesDeepLink`, `starredItemsFrom` and `setActiveSource`); a starred item of a synced local folder is dropped.
- **Synced local folders are gone** (the store's `syncedFolders`, `syncLocalFolder`, `fetchLocalFiles`… and `storageSources`): nothing in the UI added one. `/api/workspaces` no longer answers `organization_drive` (and IAM's `user_features.organization_drives` is gone): the views are the only answer.
- **Organization Files** (#1511) holds what belongs to the organization as a whole. A workspace reaches its own organization's view alone: the API reads the organization from the workspace's IAM container, never from the request, and a workspace in no organization has none (404). It needs the workspace's `files` feature. Its object storage is placed in the organization's container (`files/placement.py`), so a role held only in one of its workspaces does not reach it. Who reads or writes which folder is a policy at the organization: grant `nexus:PutOrgFile` on `${scope}/nexus:file/organization/operations/*` to let members write `operations/`, deny `GetOrgFile` on a folder to hide it. The kernel also checks the object storage action on the caller's organization role, so a viewer given `PutOrgFile` also needs `object_storage:PutObject` there.
- **IAM alone opens each view** (#1529): no workspace flag (`platform_drive_enabled` and `system_drive_enabled` are gone, columns dropped by `0073_drop_drive_flags.sql`; a PATCH still sending them is ignored). Platform Files and System Files are decided at the platform, whatever workspace the request names. `GET /api/files/views` lists, in order (`my_files`, `workspace_files`, `organization_files`, `platform_files`, `system_files`), each view with its `label`, `drive` (`file_system`), `scope` and `root` (`""` for the whole store): each is IAM's `List*` on the view's root, decided as the files routes decide it (the workspace's `files` feature for Workspace Files and Organization Files). In a View-as session My Files and System Files are not listed.
- **Files given by the workspace's offer** (ADR `20261125_offer_gives_outside_resources`; `api/app/services/iam/given_files.py`). Workspace settings › Files (`settings/files/workspace-files.tsx`) shows them: Workspace Files (the `files` feature), Organization Files and Platform Files (Off, Read, Read and write), System Files (Off, Read), each a given section of "<W> access" (`GivenOrgFiles`, `GivenPlatformFiles`, `GivenSystemFiles`) that IAM gives to the workspace's people within their level; `GET /api/workspaces/{id}/offer` answers `files` (mode, `choices`, `editable`, `reason` per row) and `my_files`, `PUT /api/workspaces/{id}/offer/files` (`{org_files?, platform_files?, system_files?}`) writes them as the caller (held-checked: the platform admin gives Platform and System Files, an org's admins its Organization Files, a workspace admin only narrows). Workspace settings › Files (`settings/files/workspace-files.tsx`) shows every kind of files in one place and writes the same: the `files` feature (`PUT /api/workspaces/{id}/feature-access`) and the given sections (`PUT /api/workspaces/{id}/offer/files`). My Files is a deployment setting (`feature_flags.viewer_my_files`). The Platform Files groups of #1590 and their two policies are moved into the offers and deleted once (`files_offer_v1`); the legacy flags (`workspace_drive_flags_legacy`) are converted into the offer by `files_offer.convert_legacy_drive_flags` (called by `access_model_v1`).
- **Where the offer is edited** (ADR `20261125_offer_gives_outside_resources`, amended 2026-11-26). Each part of "<W> access" has one editor, a workspace settings page. Access › Features (`settings/features/`) and Access › Modules (`settings/modules/`, one row per module and kind: whole, item by item or not) choose what the workspace offers; the pages under Features then show what is offered (the nav follows: the workspace's flags and resources are read again after a change). Both are policy wrappers: a Policy dropdown (`components/settings/policy-picker.tsx`, kept in `?policy=`) edits another policy the workspace owns instead (not managed), what it grants its holders within the offer, through the same routes with `?policy=<id>` (`GET|PUT /feature-access`, `GET|PUT /offer`; `FeatureAccessService._target`: 404 for a policy of another scope, 422 for a managed one; the answers carry `policy` and `policies`, "<W> access" first). Files, Search, Graphs, Maps and Ontologies edit their own part, Models its models and default (`components/settings/workspace-offer-part.tsx`: `WorkspaceOfferEditor` with `parts` and `bare`). The policy page of "<W> access" has no Configuration tab: Advanced, Builder and Code show its document.
- **Access levels** (ADR `20261126_access_levels`; `api/app/services/iam/access_levels.py`). How far people go with each Nexus feature (`feature:<key>`, its `nexus:` actions) or core service (`service:<service>`: triple store, object storage, vector store, datasets, documents, secrets, key-value, cache, events), kept apart: a level `none`/`read`/`write`/`admin`. In "<W> access" a cap (`AccessLevelCap` Denies above it, everyone in the workspace, admins included); in another policy a grant (`AccessLevelGrant` Allows up to it). `GET|PUT /api/workspaces/{id}/access-levels?kind=feature|service&policy=<id>` (`FeatureAccessService.read_levels`/`save_levels`). Access › Features lists each Nexus feature with its description, its level in one Access column (None takes it out of the policy, `nobody`, and caps it at none; any other level puts it in, `everyone`, at that level: `levelPlan`; a feature taken out shows None whatever level is stored), saved with Save, and a link to its settings page; Access › Services (`settings/core-services/`) sets the core services, each change at once. A feature's group includes its `UseFeature` gate, so `none` denies the feature itself. Organization › Access › Features, Services and Modules (`app/organizations/[orgId]/settings/{features,core-services,modules}`) render the same components on `org:<id>` (`lib/access-model/target.ts`; API `/api/organizations/{id}/feature-access|offer|access-levels`): "<O> access", whose Denies reach every workspace of the organization; a workspace's Features page hides what its ceiling does not offer.
- **A module app and Platform Files: two patterns.**
  - *App-mediated*: the module's own service account does the storage I/O (`object_storage` as `module/<project>/<module>`, with what its manifest was approved for). The user never touches the platform drive; the module decides who may ask it, and needs no Platform Files on the user's side.
  - *User-mediated*: the module calls the Files API (`/api/files?scope=platform_drive`) with the user's token, so the user needs Platform Files (their workspace gives it, or a policy at the platform). Ask first with `may_use_platform_files(user_id)` (`services/files/adapters/primary/files__primary_adapter__dependencies.py`: IAM's `nexus:ListPlatformFiles` at the platform, as `GET /api/files/views` decides it); it replaces the removed `workspace_setting(..., "platform_drive_enabled")`.
- **Staff folders.** Workspace Files, Organization Files and Platform Files get the nine staff folders and their README (`assets/staff_folders/`).
- Tests: `lib/drive-label.test.ts` (view mapping, Drive and View choices, All Views, old sources), `lib/files-route.test.ts` (old `?source=` links), `lib/drive-settings.test.ts`, `stores/files-views.test.ts` (starred items, the open view, no synced folders), `hooks/use-file-views.test.ts`.

### Responsive layout

Mobile list-detail breakpoints live in `browse/browse.css` and `components/files-components.css`. Below 768px, the shell shows `FilesSection` on `/files` and the browser on `/files/browse`. Desktop renders the browser at `/files` directly.

### Route convention

Each route segment keeps three files where applicable:

```
{segment}/page.tsx   → export { default } from './{segment}';
{segment}.tsx        → route component (imports shared components + segment.css)
{segment}.css        → route-specific semantic styles only
```

Semantic class prefix: `files-browse-*` for route layout and desktop chrome, `files-mobile-*` / `files-add-sheet-*` for shared mobile chrome. Use `var(--space-*)`, hex tokens from `globals.css`, and `var(--org-border-radius, 0px)` on buttons and cards.

Pilot reference for desktop chrome: `files/browse/browse.css` + `browse.tsx`. Mobile chrome: `files/components/` + `files/browse/browse.css`.

## Datasets UI module

Datasets is the tabular warehouse, not Files (blobs) and not Maps (GIS layers). It sits next to Files in the primary nav. The engine `DatasetService` stores named, partitioned SQL tables; Nexus is a read-only primary adapter: list, describe, preview, guarded SQL.

```
src/app/workspace/[workspaceId]/datasets/
├── page.tsx                      → export { default } from './datasets';
├── datasets.tsx                  # Desktop catalog
├── datasets.css
├── [namespace]/[name]/
│   ├── page.tsx                  → export { default } from './table';
│   ├── table.tsx                 # Schema + preview + SQL
│   └── table.css
├── lib/
│   ├── datasets-route.ts
│   └── datasets-route.test.ts
└── components/
    ├── datasets-section.tsx      # Sidebar + mobile list
    └── datasets-components.css

apps/api/app/services/datasets/   # Hexagonal domain wrapping DatasetService
```

HTTP: `GET /api/datasets`, `GET /api/datasets/{namespace}/{name}`, `GET .../preview`, `POST /api/datasets/{namespace}/query`. Feature flag: `datasets` (on for owner/admin/member/viewer). The warehouse is process-global; workspace membership is required but tables are not isolated per workspace. Write/drop is not exposed.

Mobile: `/datasets` = namespace list, `/datasets/{namespace}/{name}` = table detail.

## Chat UI module

The workspace chat surface is a self-contained module under `apps/web/src/app/workspace/[workspaceId]/chat/`. Phase 1 established route structure and thread detail; Phase 2 colocates conversation list chrome with semantic CSS. Thread UI (`chat-interface.tsx`) semantic migration is Phase 3.

### Structure

```
src/app/workspace/[workspaceId]/chat/
├── [[...slug]]/
│   └── page.tsx                  → export { default } from '../thread/thread';
├── lib/
│   ├── chat-route.ts             # parseChatRoute, newChatPath, nextChatUrl
│   └── chat-route.test.ts
├── components/
│   ├── chat-components.css       # Shared list chrome semantic styles
│   ├── chat-section.tsx          # Conversation list (sidebar + mobile list)
│   ├── conversation-item.tsx     # Single conversation row + context menu
│   └── project-group.tsx         # Project folder group
└── thread/
    └── thread.tsx                # Header + ChatInterface (thread detail)
```

### Shared components

| Component | Purpose | Used by |
|---|---|---|
| `ChatSection` | New chat, agents, skills, pinned/recent conversations | Shell sidebar panel, mobile list (`detailOnly`) |
| `ConversationItem` | One conversation row with pin/rename/archive/delete menu | `ChatSection`, `ProjectGroup` |
| `ProjectGroup` | Collapsible project folder with nested conversations | `ChatSection` |

### Shell vs module ownership

| Concern | Owner | Notes |
|---|---|---|
| Conversation list (desktop panel + mobile list) | Module (`chat/components/chat-section.tsx`) | Shell imports module; `sidebar/chat-section.tsx` re-exports for compat |
| Thread detail | Module (`thread/thread.tsx`) | `/chat/new`, `/chat/{id}` via optional catch-all |
| Route parsing | Module (`lib/chat-route.ts`) | Imported by shell layout, sidebar, and `chat-interface.tsx` |

Route parsing lives in `lib/chat-route.ts` and is imported by `workspace-layout.tsx`, `chat-section.tsx`, `mobile-top-bar.tsx`, and `chat-interface.tsx`.

### Cited links

An answer's sources are every `http(s)` URL of its text, its tool outputs and its sources, so text an agent read chooses them. `components/chat/citation-frames.ts` decides how they are framed: a page of this app or of the API is never framed (it opens in a new tab), the hidden embeddability probe is `sandbox=""` (no script, an origin of its own), and the preview panel's sandbox never holds `allow-same-origin`. Tests: `citation-frames.test.ts`.

### Semantic CSS

List chrome uses `chat-*` prefixed classes in `components/chat-components.css`. Use `var(--space-*)`, hex tokens from `globals.css`, `var(--org-border-radius, 0px)`, and `var(--workspace-accent, …)` for tenant-themed active/hover states. Mobile list panel rows use `.is-mobile-panel` (min-height 44px, larger touch targets), matching shell mobile list patterns for Account/Files.

### Route convention

URLs are unchanged:

- `/workspace/{id}/chat`, conversation list (mobile) / launcher (desktop)
- `/workspace/{id}/chat/new`, blank thread
- `/workspace/{id}/chat/{cid}`, existing thread

The optional catch-all `[[...slug]]/page.tsx` re-exports the thread module so all three paths share one page component without a separate index route (which would conflict with the catch-all on `/chat`).

### Phase 3 (not yet)

- Migrate `chat-interface.tsx` to semantic CSS

## Settings

One place, one door, four tabs: **Platform**, **Organization**, **Workspace**, **Account**, from the widest level to the narrowest, as what a change there touches (the instance, all of an organization's workspaces, this workspace, you).

- **One door**: the dock's Settings opens Settings at the last settings page visited (`useSettingsHref`: `settingsReturnPath`, else this workspace's settings when the caller opens them, else `/account/profile`; a page of another workspace's settings is not reopened from this one). A layout remembers a page (`useRememberSettingsPath`, the level's too) only once its own gate lets it open: not while the access is read, not refused, not an index or a URL that redirects.
- **Account and session**: the identity row (the dock's, the phone's top bar) opens the account menu; Account (`ACCOUNT_SETTINGS_PATH` in `components/shell/user-avatar.tsx`) opens `/account/profile`. Help (the workspace's `/help`) and Log out (`useAuthStore().logout()`, which also forgets the remembered pages, then `/auth/login`) sit at the right of the Settings header (`SettingsShellHeader`) on every page of every level; a phone shows their icons alone. Help opens to every member of the workspace, whatever features they hold (`getGatingFeatureForWorkspacePath` answers null for `/help`).
- **Tabs**: the shell's header reads Settings, with a tab bar under it (`SettingsShellHeader`). A level has a tab only when the caller may open something there, and with one level (a plain member: Account) there is no tab bar. The active tab is the page's level, from its URL (`currentSettingsLevel`); a tab opens its level at the last page visited there (`settingsLevelReturnPath`, while that is still one of the level's pages), else at its first page. The model is pure (`settingsLevels`, `currentSettingsLevel`, `settingsTabs` in `components/settings/settings-levels.ts`), read by `useSettingsLevels` and `useSettingsTabs` (`hooks/use-settings-levels.ts`), which every layout calls once.
- **The column lists the active level alone** (`SettingsLevelsNav`): Platform, every group the caller holds, each under its heading (Administration, System with Layers and Diagrams, Activity, Resources, Data: `platformSettingsGroups`); Organization, its sections, then "Other organizations" when the caller opens several; Workspace, its General group, then Features; Account, Profile and Appearance.
- **Each level, its own pages' rule**: Platform, `visiblePlatformSettingsGroups` over the caller's platform actions (`GET /api/iam/admin/access`), the tab shown when it is not empty; Organization, `orgSettingsNavForRole` with the caller's role there and IAM access (an organization's settings page passes the one it read); Workspace, `useWorkspaceSettingsAccess` and `visibleSettingsGroups`; Account, `accountSettingsNavVisible`. The tab reads "Organization" whichever organization it opens; with several, the others are listed under "Other organizations". Who sees what, person by person (platform admin, organization admin, workspace owner, delegated `iam:` at a workspace or an organization, member, viewer, system reader, user lister: their tabs, and the column of each), is `components/settings/settings-access.test.ts`: the real hooks over a fake API.
- **By URL**, each layout keeps its own gate (Platform: the 403 page; Organization and Workspace: "You have no access to these settings"); on a refused page a caller with one level still has its column.
- **Phone**: the list, then a page. The tabs sit at the top of the list screen and scroll sideways; a tab opens its level's list (`/settings`, `/organizations/<id>/settings`, `/workspace/<id>/settings`, `/account`); a page has the back button and no tabs. The index pages send a computer to the first page only once the viewport is known (`isMobileViewport`).
- The four layouts (`app/settings/`, `app/organizations/[orgId]/settings/`, `app/workspace/[workspaceId]/settings/`, `app/account/`) share the shell; the workspace's chrome steps aside on its settings (`WorkspaceLayout`, `isWorkspaceSettingsPath`). People of a level are its **Members** (workspace, organization); the platform's accounts are **Users**. Sign-out forgets the remembered pages (`forgetSettingsPaths`, the Console's old key included).

Decisions:

- **One Settings, four levels.** Decision: the per-level doors (workspace settings in the dock, Account / Organization / Platform in the avatar menu, a scope switcher in each shell) became one Settings, a tab per level. Consequences: the dock's settings column and the scope switcher are gone (`settings` is a retired panel section); the dock's Settings is offered to everyone (Account at least); each level's URLs are unchanged.
- **Account menu.** Decision: the identity row (the dock's, and the phone's top bar) opens the account menu: name and email, the current workspace and role, Find workspace, Account, Settings, Log out. Account is the row that opens `/account/profile`. Help stays beside Log out in the Settings header.
- **No Console: the platform is one tab.** Decision: the Console split of 52bda6c5a (System, Activity, Resources and Data in a Console of their own, from the avatar menu, the Platform level being Administration alone) is reverted; Platform holds every platform page again. Why: the Console was defined by subtraction (what remained once Administration was taken out); "what you watch" was false, since its pages change things too (trigger and cancel jobs, cancel agent runs, evict modules, write engine secrets); and it put one noun in two areas (Models in Workspace settings and in the Console). Consequences: the avatar menu is Settings, Help, Log out; `/settings/console` redirects to `/settings` (`lib/redirects.ts`); `consoleGroups`, `isConsolePath` and the `console` area of remembered paths are gone, and sign-out still clears its key. What the split moved stays: Infrastructure is Platform › System › Layers and Diagrams (`/settings/system/layers`, `/settings/system/diagrams`, `nexus:ReadSystem`), its former workspace URLs redirect there, and `scripts/build_abi_architecture.py` writes the snapshot to `system/infrastructure/`.

### Platform

`/settings`, outside any organization or workspace: `apps/web/src/app/settings/`, on the shared settings shell (`components/settings/`).

- **Column** (`lib/nav.ts`, `platformSettingsGroups`): Administration (General, Organizations, Users, Drives), Access (Groups, Policies, Service accounts, Module approvals, Simulator, Audit, Models: the model sets, `iam:ListPolicies`), System (Overview, Services, Modules, Discovery, Agents, Jobs, NATS, Bus, Layers, Diagrams), Activity (Live traffic, Traces, Events, Event store, Activity log), Resources (Models, Secrets, Email, Source control, Coding environments), Data (Nexus tables, Knowledge graph, Vector store, Documents, Datasets, Object storage, Key-value, Cache). Every group has a heading, shown on the desktop column and the phone list alike; a group with nothing the caller holds is left out, heading included. Each item declares what it needs: `nexus:ListUsers` or `iam:ListAttachments` for Users, `nexus:ListDrives` for Drives, its own actions for each page of Access (`ACCESS_SECTIONS`; Audit `nexus:ReadSystem`), `nexus:ReadSystem` for the rest. The shell reads the caller's actions from `GET /api/iam/admin/access` (`hooks/use-platform-settings-access.ts`), shows the items they hold and a 403 page when there are none or for a page they do not hold. Callers at the same time share one request; a failed one keeps the user's last answer, and with none shows an error with Try again. The Platform tab is shown whenever an item is available. The API checks every call itself (`require_superadmin`: `ReadSystem` to read, `ManageSystem` to change; the Users routes their `nexus:*User` action, then IAM's and the provider's own as the caller: `services/accounts`; IAM's own `iam:*` checks).
- **Nexus tables** (`tables/`): the table of tables (sections, counts, search, facets, inline schema, Export all as JSON or xlsx), then `/settings/tables/<name>` (grid, Export CSV/xlsx, a close button beside it that returns to Nexus tables as it was left: `lib/tables-view.ts`), then `/settings/tables/<name>/<row id>` (back link; on `users`, the superadmin toggle for whoever holds `ManageSystem`). The list, labels and sections come from the API (`GET /api/admin/tables`, the registry `api/app/core/platform_tables.py`); the web app keeps no copy.
- **Organizations** (`organizations/`, `nexus:ReadSystem`): every organization the caller may list (`GET /api/organizations`, IAM-filtered: the platform admin sees all), each with its slug, id and a link to its Organization settings. Create (name, a slug suggested from it: `POST /api/organizations`, "Slug already exists" said inline), rename inline (`PATCH /api/organizations/<id>`), delete (`DELETE /api/organizations/<id>`, `DeleteOrganization` on its container) once its name is typed back (never `confirm()`). An organization that still has workspaces is refused (409): the API names them, and the row shows its words. Calls in `organizations-api.ts`, pure helpers in `organizations-model.ts` (`PLATFORM_ORGANIZATIONS_PATH`, imported by the middleware's redirects too: `/settings/organizations` is a section, never an old link to the `organizations` table, which is at `/settings/tables/organizations`); tests `organizations-model.test.ts`, `organizations.test.ts`.
- **Users** (`users/`, `nexus:ListUsers`): every account of the platform and the people invited who have no account yet (`GET /api/admin/users`; an invitee's row id is `invited:<email>`), with the organization Users page's table: name and email, IAM id, status ("Signed in" at least once / "Invited, not yet", and a Deactivated mark), superadmin, organizations, created; one search over every column, a filter with facets and a sort on each column, Export CSV/xlsx of the visible rows (the shared `components/settings/users-table/`: `users-table-filter.ts`, `users-table-export.ts`, which Organization settings and Nexus tables import too). A row with an IAM id opens the person's page under Users (`/settings/users/<IAM id>`, `personHref`, `platform-person.tsx`), where their roles, groups and policies at every level are seen and attached, and their "Platform access (automatic)" is read by their IAM id alone (`GET /api/admin/users/<IAM id>/access`, never the directory, #1608); the list itself shows no access. The lifecycle, each button shown for its action in `GET /api/iam/admin/access` at the platform (`USER_ACTIONS`): Invite (`nexus:InviteUser`; email, name, the provider when there are several: `POST /api/admin/users/invite`, the invitations of `services/invites`, then what was done: account made at the provider, provisioning withheld, mail sent, the provider's warning), edit the name and superadmin on or off (`nexus:UpdateUser`; `PATCH /api/admin/users/<id>`, superadmin for an account only), Deactivate and Reactivate (`nexus:SuspendUser`, `nexus:ResumeUser`; `POST …/deactivate`, `…/reactivate`: no sign-in at the identity provider and no API call, data and memberships kept), Delete (`nexus:DeleteUser`): the row reads `GET …/deletion` and says what goes (the account at the identity provider, or that a provider which manages its people keeps it; the IAM user with its attachments and groups; each membership; sessions; API keys; pending invitations) and what stays (what they wrote in the workspaces it names), shows the API's reason when it is `blocked`, and sends `DELETE …?confirm=<email>` once the email is typed back (never `confirm()`). None of it is offered on oneself (the row of the signed-in user, by Nexus or IAM id); the API refuses it too, and the last platform admin, with words the row shows. A change answers the row as it now is (with the provider's `warning`, shown under it). Calls in `users-api.ts`, pure helpers in `users-model.ts` (`PLATFORM_USERS_PATH`, imported by the middleware's redirects: `/settings/users` is a section, its old row links go to the `users` table); tests `users-model.test.ts`, `users.test.ts`.
- **Old links** redirect in `middleware.ts` (`lib/redirects.ts`): `/settings/<table>[/<row>]` (and `<name>_table`) to `/settings/tables/...` (`/settings/users` is the Users page and `/settings/users/<IAM id>` a person's; `/settings/users/user-<hex>`, a row of the old table page, goes to `/settings/tables/users/<row>`), `/workspace/<id>/admin/system?tab=<tab>` to the System page (Access to `/settings/access`, other query parameters kept), `/settings/system/access` and `/settings/modules` (the removed Modules & features) to `/settings/access`, `/settings/roles?section=…` to the page of Access it opened (People & roles to Users, `oldAccessRedirect`), `/settings/console` (the removed Console) to `/settings`, `/workspace/<id>/admin/events` to `/settings/system/events`; Organization settings' Access and Modules & features (`/organizations/<org>/settings/access`, `/settings/modules`) to its Access › Policies (`organizations/[orgId]/settings/lib/redirects.ts`). The legacy workspace links (`/settings/members`, `/settings/policies`, `/settings/permissions`, ...) still go to the workspace.
- **Phone**: `/settings` lists the items under the tabs, an item opens full screen with back to the list; a table's back (and close) goes to Nexus tables, a row's to its table.

Decisions:

- **One table list, the API's.** Decision: Platform Settings reads the tables from `GET /api/admin/tables`; `core/platform_tables.py` holds each table's label, section and description, and `EXCLUDED_TABLES` every table it never serves, with the reason. Consequences: adding a table to nexus.db fails `platform_tables_test.py` until it is listed or excluded; the web app needs no change for a new table. Credential columns are masked by name (`SECRET_COLUMN`, `REDACTED_COLUMNS`), a test lists every column that looks like one and has it masked or named as harmless, and a table keyed by a credential has no row pages.
- **The sidebar follows permissions, not a role.** Decision: each item names the action it needs and the shell asks IAM (`GET /api/iam/admin/access`) once per visit. Consequences: a delegated IAM admin without `nexus:ReadSystem` sees the pages of Access IAM opens to them alone; a stranger gets the 403 page; Nexus adds no role check, and hiding an item never replaces the API's.
- **No modules × workspaces page.** Decision: Platform Settings › Modules & features and Organization settings › Modules & features (the sets matrix) are removed with the sets; their URLs redirect to Access › Policies, where policies decide what each organization and workspace may use. Consequences: `src/app/settings/modules/`, `organizations/[orgId]/settings/modules/` and the `sets` client of `src/lib/iam-admin/` are gone; Organization settings › Workspaces and Workspace settings › General no longer link to them.
- **Users is the directory and each person's page.** Decision: Platform Settings › Users lists accounts and changes their lifecycle (invite, name, superadmin, deactivate, delete), and each row opens the person's page under Users for their roles, groups and policies at every scope (People & roles, which listed the same people, is gone: see "Policies are first-class"). Consequences: the list shows no role or policy and attaches nothing, the person's page does; the raw `users` table stays at `/settings/tables/users`; an organization's admin, who holds no `nexus:*User` action at the platform, does not see the page.
- **System lives in Platform Settings.** Decision: the System app's views are Platform Settings pages, and the dock and mobile More sheet no longer offer System or Events. Consequences: its code moved from `app/workspace/[workspaceId]/admin/system/` to `app/settings/system/` (Events to `system/events/`, with its feed beside the graph instead of in the workspace's second sidebar); its Access tab became Platform Settings › Access (`/settings/access/<page>`), the shared Access UI at platform scope ("Access UI module").

## System (platform super admins)

Platform Settings › System: `/settings/system` (Overview) and `/settings/system/<view>` (Services, Data, Jobs, Agents, Modules, NATS, Live traffic, Traces, Events), shown to whoever holds `nexus:ReadSystem`. Live traffic is an SSE stream read with raw `fetch` and `getAuthHeader()` (like chat), started and stopped by the user.

- Workflows REST: `apps/api/app/services/workflows/` (see its `AGENTS.md`), mounted at `/api/workflows`, for platform admins, signed in or with their personal API key (`require_superadmin`, decided by IAM).
- API: `apps/api/app/services/sysadmin/` (hexagonal, see its `AGENTS.md`), mounted at `/api/admin/system/*` behind `require_superadmin` on the router. `main_public_routes_test.py` fails if a route there loses it.
- Web: `apps/web/src/app/settings/system/`: one `page.tsx` per view rendering `SystemPage` (`system.tsx`: the page title, Refresh, the view), colocated modules (`system-api.ts`, `system-model.ts`, `system-tabs.ts` for the views and their paths, one component per view) and jsdom render tests. Views poll every 10 s while visible, one call at a time (`usePoll`); Refresh reloads the open view.
- Data: `settings/system/data/`, a three-pane explorer (service rail, browser, inspector) over `/api/admin/system/resources`.
  - The shell owns layout, state (`use-explorer.ts`), URL deep links (`?service=&in=&item=`), keyboard shortcuts (`?` lists them), dialogs (typed-confirmation delete, Monaco editor, custom create), toasts, history and recent changes. Do not fork it per service.
  - Each service is one `ServiceView` in `data/services/<service>.tsx` (contract in `services/types.ts`, registered in `services/registry.ts` as a loader: it loads when its page opens, and its icon and label are also in `lib/nav.ts` `SERVICE_ICONS` and `lib/service-pages.ts`). It sets per-depth columns or cards, icons, nouns, badges, summaries, facts, a custom preview, an editor spec or a custom create form, and the delete copy. Its styles live in `services/<service>.css` (`data-<service>-*`).
  - Shared renderers live in `data/viewers/`: JSON tree, Monaco code, data grid, RDF triples, vector, email, message, status, binary (hex dump and images), and LangGraph checkpoints (`checkpoint-view.tsx`: transcript with tool calls, models and tokens; state, pending writes, metadata; "The step before" opens the parent through `PreviewContext.open`). In Documents, the saver collections list as "Step N · source" rows grouped by thread (`title` hook on `ServiceView` for entries whose name is an opaque id). Adapters send a structured `view` (shapes in the API's `resources.py`) and the generic preview picks the renderer.
  - Secrets stay masked until Reveal (shown for a while, then hidden again). Replace and Delete need the id typed back. The API audits every change and reveal before it runs. Never use browser `confirm()` dialogs here.
  - Tests: `data/*.test.ts` (shell flows with an in-memory API), `data/viewers/*.test.ts`, `data/services/*.test.ts(x)`.
- Jobs: `settings/system/jobs/` over `/api/admin/system/jobs`, a Dagster-like view of module jobs (engine and remote).
  - Jobs list: failing and running first, schedules in plain words with a live next tick, a strip of the last 20 runs, and queue depth.
  - Job page: triggers (with a schedule's input), health (success rate, average duration), queue, settings, its runs; a workflow's input and output schemas.
  - Workflows (`kind: "workflow"`) show a "workflow" badge and, once any exists, an All / Jobs / Workflows filter (`?kind=`). Plain jobs render as before.
  - Run now and Re-run on a workflow open a form generated from its input schema (`schema-form.ts` builds the fields and validates, `schema-fields.tsx` renders): strings, numbers, integers, booleans, enums, lists of those and nested objects, with `$ref` to the schema's `$defs` and pydantic's optional wrappers followed. A schema with anything else (unions, lists of objects, free-form objects) gets the JSON editor only; the editor is also a tab beside the form. The input is checked in the browser before sending, and the API's own 422 faults show under their fields.
  - Run feed with status filters.
  - Run inspector: a trigger → start → finish timeline with the wait before start, the error, logs (`ctx.log`), payload, result, and the run's trace (the Traces waterfall, embedded). A workflow run opens on a **Steps** tab (`run-steps.tsx`): each step's status, attempt, start offset and duration on one time axis, its error, and a link to the child run a `call` step started. A result the API cut for display says so.
  - Run now, Re-run and Cancel are audited by the API. It reuses the Data tab's atoms, viewers, modal and toasts (`../data/`) and polls only while visible: 5 s, or 1.5 s for a live run.
- Access (`/settings/access/<page>`, the former Access tab, then Roles & permissions) is the shared Access UI at platform scope, one page per section: see "Access UI module".
- Tests: jsdom render tests beside each view (`system-render.ts`, which re-exports `src/lib/testing/mount.ts`) and pure model tests.
- Traces: `settings/system/traces/` over `/api/admin/system/traces`, so nobody needs the Jaeger UI. The API reads the tracing backend's query API (Jaeger `/api/v3`, `telemetry.query_url`, else `telemetry.ui_url`); the browser never talks to Jaeger.
  - Search by service, operation, time window, minimum duration and errors only, or jump to a trace id. Results are a duration-over-time scatter plus a list.
  - Trace: a waterfall (`waterfall.tsx`) in span-tree order with service colors, self time, events as ticks, a minimap to drag-zoom (double-click a span to zoom to it), a span filter that keeps ancestors, collapse and expand, and ↑/↓/←/→. Above 300 visible rows it renders only the rows on screen.
  - Repeated calls fold: 5 or more siblings with the same service and operation (polling, saves) become one row with the count, total time, cadence (`every …`) and a tick per call, placed where the first starts. Unfolding lists one collapsed row per call. A toolbar toggle shows every call; filtering always lists matches flat; a selected or linked span opens the groups and spans above it (`layoutRows`, `pathTo` in `traces-model.ts`).
  - Span detail: timing, parent and children, attributes grouped by namespace (`abi.`, `messaging.`, `rpc.`, `http.`…), events, resource and links to other traces.
  - Deep links: `/settings/system/traces?trace=<id>&span=<id>` (`systemTracePath`). Live traffic trace ids and the Jobs run inspector open here (`TraceView` is embeddable with `compact`); Jaeger stays a secondary link when `ui_url` is set.
  - Pure helpers (tree, self time, ticks, placement, filters) live in `traces-model.ts`; tests in `traces/*.test.ts` with `traces-fixtures.ts`.
- A source that is down (NATS mode off, discovery not configured, `nats.monitoring_url` unset or unreachable) never fails a whole view: the API returns the others plus a reason, or a 503 `{source, reason}` for NATS-only views, and the page shows that reason.

## Access UI module

One set of components manages access at every level: `apps/web/src/components/access/`, over `/api/iam/admin` (API: `apps/api/app/services/iam_admin/`, see its `AGENTS.md`). The scope is its one parameter; what the caller may do there, as IAM answers `GET /api/iam/admin/access?scope=`, is the only thing that decides the pages and buttons. Each page of Access is a page of the settings, with its own address (`access-paths.ts`); a policy's and a group's page is `<page>/<id>`, a person's is under Users or Members.

| Page | Address | Scope | Shown to |
|---|---|---|---|
| Platform Settings › Access › Policies, Groups, Service accounts, Module approvals, Simulator, Audit (`app/settings/access/`) | `/settings/access/<page>[/<id>]` | the platform (`PLATFORM_ACCESS_SCOPE`) | whoever holds one of the page's actions at the platform (`ACCESS_ITEMS` in `settings/lib/nav.ts`) |
| Platform Settings › Users › a person (`app/settings/users/[personId]/`) | `/settings/users/<IAM id>` | the platform | whoever opens Users (`nexus:ListUsers` or `iam:ListAttachments`) |
| Organization settings › Access › Policies, Groups (`organizations/[orgId]/settings/{policies,groups}/`, `components/org-access.tsx`) | `/organizations/<org>/settings/<page>[/<id>][?in=<ws>]` | the organization, its workspaces one pick away | whoever IAM lets open the page at `abi:nexus:organization/<org>` (`needs: <page>` in `lib/nav.ts`), whatever their role |
| Organization settings › Members › a member (`users/[userId]/member-access.tsx`) | `/organizations/<org>/settings/users/<id>` | the organization | its admins, and an `iam` holder there opening a holder's page |
| Workspace settings › Access › Policies, Groups (`workspace/[workspaceId]/settings/{policies,groups}/`, `workspace-access.tsx`) | `/workspace/<ws>/settings/<page>[/<id>]` | the workspace (`abi:nexus:organization/<org>/nexus:workspace/<ws>`, `abi:nexus:workspace/<ws>` for a personal one) | whoever IAM lets open the page there (`needs: <page>` in `components/shell/settings-nav.tsx`); Members stays everyone's door |
| Workspace settings › Users › a user (`users/[personId]/`) | `/workspace/<ws>/settings/users/<IAM id>` | the workspace | its admins, and an `iam` holder there |

A group's page (`components/access/groups/groups.tsx`) renames a group the level owns for whoever may `iam:UpdateGroup` (`PATCH /api/iam/admin/groups/{id}`). The access policy and the two groups of an organization or a workspace follow its name on their own (`apps/api/app/services/iam/AGENTS.md`, "Access policies and default groups"): rename the container, not them.

```
src/components/access/
├── access-page.tsx             # AccessPage({ section, scopes, focus, hrefs }): one page of Access, the scope picker, what its address opens
├── access-paths.ts             # each level's Access and person addresses; oldAccessRedirect (Roles & permissions URLs)
├── access-scope.ts             # AccessScope (level, value, org, workspace); ownerOf, ownedHere
├── access-sections.ts          # each page and the actions that open it; LEVEL_SECTIONS; opensAccess (the menus)
├── access-directory.ts         # the people of a scope (workspace or org members), for People and groups
├── access-props.ts             # AccessViewProps: api, can, scope, directory, nonce, open (AccessNavigation)
├── access-base.css, access.css # the module's own base styles (tables, buttons, inputs) and shell
├── people/                     # a person's page (person.tsx, PersonPage in person-page.tsx); the holders list Users shows an iam:ListAttachments holder (people.tsx)
├── groups/                     # the scope's groups: create; a group's page: members, its attachments at every level; IdP claims where offered
├── holdings/                   # a principal's access at every level: rows (holdings-model.ts: levelLabel, roleTargetOf) and HoldingsTable
├── policies/                   # the tree of policies (policy-tree.ts), the editor, where a policy is attached (policy-attachments.tsx), the Statements view
│   └── builder/                # the policy builder (builder-model.ts: publishers → type → actions → resources → statements)
├── roles/                      # role-change.ts (memberships)
├── attachments/                # AttachForm, scopeLabel
├── service-accounts/, approvals/, simulator/, audit/   # what the platform administers
└── access-page.test.ts         # permission profiles: every kind of caller, every page, at the three scopes
```

- **Pages** (`access-sections.ts`, any of a page's actions opens it), groups first: Groups (`iam:ListGroups`), Policies (`iam:ListPolicies`, `iam:CreatePolicy`: whoever may only create builds one, with no list; or `iam:ListAttachments`: the policies held here and who holds each), Service accounts (`iam:ListPrincipals`), Module approvals (`iam:ListManifests`), Simulator (`iam:Explain`), Audit (`nexus:ReadSystem`). An organization and a workspace have Groups and Policies (`LEVEL_SECTIONS`). A page the caller may not open says "You cannot manage <page> here."; the settings menus list a page on the same rule (`visibleSections`, `opensAccess`), and Organization and Workspace settings wait for the access read before sending an `iam` holder to the first page they hold (`orgSectionRedirect`, `settingsLandingPath`). The page's Refresh reads the access again (`useIamAccess(..., { reload })`).
- **The holders on Users** (`people/people.tsx`, Platform Settings › Users for whoever may `iam:ListAttachments` and not `nexus:ListUsers`, `users/platform-holders.tsx`): who holds what at the platform: each person's built-in role (from the directory; the organization's owners and admins read-only "from organization" at a workspace), the policies attached to them there, and what reaches them through a group holding policies there. At the platform, the unscoped attachments. A role changes through `changeMemberRole` (the Members pages' code); what IAM attaches with it (`builtin.platform.member|viewer`: `isRoleCompanion`) is shown with the role, never detached or offered; other policies attach and detach here (`AttachForm`, which never offers a person a built-in role: that is a membership; offers a service account's policy, `builtin.api`, `builtin.engine`, `builtin.idp`, `builtin.job`, `builtin.module_bootstrap` or a module's `module.*`, to a service account only; never `builtin.self` to a person or a group (every user holds it already, with no attachment); starts with no policy chosen, so one click attaches nothing; a typed id's kind comes from its prefix, `grp_`, `sa_`). What could not be read (the members, a group's members) is said above the table, the rest shown. Each name opens that person's page (a group's, its page). At the platform, for whoever may `iam:ListPrincipals`, the filter is also IAM's search (`GET /principals?q=`, two characters or more): the people it finds who hold nothing at the platform are listed below the table, each opening their page.
- **A person's page** (`people/person.tsx` in `people/person-page.tsx`; under Users or Members, `platformPersonPath`, `organizationPersonPath`, `workspacePersonPath`): every role, policy and group they hold, at every level IAM lets the caller list, whatever the level of the page it is opened from: `GET /attachments?principal_id=` (across levels), `GET /principals/{id}/groups` (IAM's `list_principal_groups`) and every group's attachments in one `GET /attachments?principal_id=<g1>&principal_id=<g2>…` (`attachmentsByPrincipal`, #1608). One table (`holdings/HoldingsTable`) from the top level down: the role or policy (a link to the policy at its owner, `ownerHref(policy_owner_scope, id)`, when the caller may manage something there), its level (`levelLabel`: as the Owner column names containers, `ownerLabel`, a scope below a container "and all below it"), whether it is direct, comes with a role (a companion: `builtin.platform.member` with a member, admin or owner role at a workspace or below a container, `builtin.platform.viewer` with a viewer one; the row names the roles it comes with, "Comes with Member at Workspace W (Acme)", `HoldingRow.broughtBy`) or through which group (a link to its page), and the detach where `access` at the row's level gives `iam:DetachPolicy`. A role row is a membership: changed as on Members (`changeMemberRole` at the organization or workspace it is at, `roleTargetOf`, `assignableRoles`, `roleChangeable`), with `iam:AttachPolicy` there, for the person as that level's members name them (`person.tsx` `memberAt`: their IAM id, else the member with their email, an account linked from the old login), whatever opened the page; someone not found among those members, or whose role there is the organization's, is read-only, and so is one's own role. The org-wide mirror and what comes through a group are read-only. A policy is attached to them from the page (`AttachForm`, the person fixed as a user, so no built-in role and no service account's policy is offered): at the page's level by default, or at another level they belong to (the platform, or an organization or a workspace where they hold a role), among those where `access` gives `iam:AttachPolicy`; the page reads what they hold again, so the new row shows at once. Then their groups, each with its owner's level. Across levels nothing is refused: holding nothing the caller may list reads "They hold nothing you may list."
- **The Groups list** reads each group's member count with the list (`GET /groups?member_counts=true`, pages of 500 followed by `listAllGroups`): "–" where IAM would refuse the group's detail; no detail is read per group (#1608).
- **A group's page** (`<level's Groups>/<id>`, in place of the list): its members as IAM lists them (each opening their page), and every attachment of the group at every level, in the same table; a group owned elsewhere is shown, never changed.
- **Who holds a policy** (`policies/policy-attachments.tsx`, "Who holds it", first on a policy's page, a built-in role's included): `GET /attachments?policy_id=` across levels, to whom (a link to the person's or the group's page) and at which level, with the detach where `access` there allows it; never for a role or its companion (a membership). With `iam:AttachPolicy` at the page's scope and the policy among `GET /attachable` there, it is attached from the page to a member, a group or (at the platform) a service account (`offeredTo`: never a built-in role to a person). One attached nowhere reads "Attached nowhere you may list."
- **Opening the pages.** A name links to a person's page where the level has one the caller opens (`AccessHrefs.person`: under Users for whoever opens Users; under Members at an organization or a workspace), and to a group's page only where Groups is shown (`AccessNavigation`'s `group` is absent otherwise). A change of scope (the organization's "Manage" picker, `?in=<ws>`) opens that scope's list: what was open was judged at the scope left. The page's Refresh reads the pages again, the rights at each level (`useActionsAt`) and the containers' names included; an answer that failed is asked again then, never kept.
- **Groups**: the scope's own (created with `scope`), with their members (picked from the scope's people) and their attachments at every level (the group's page); a group owned above is attached to, never changed. IdP group claims show where `access` offers `iam:MapIdpGroup` (the platform).
- **The access model (#1583, #1588).** The names of the model are `src/lib/access-model/` alone (`levels.ts`: the level groups and policies, "<W> workspace", "<W> admins", "<O> admins", "<O> people", the capability groups; `workspace-offer.ts`; `model-sets.ts`; `workspace-create.ts`). Groups lists the model's groups first (`groupKind`, from the markers `membership_of` / `level_group` of `GET /groups`, else the name and owner): levels, org admins, workspace admins, workspaces, org people, capabilities, then custom; above the list, the generic level policies ("Viewer access", "Member access", "Workspace admin access") in plain words, read-only, and the capability groups ("Workflow runners" at an organization, "Models · all" at the platform; `GET`/`POST /api/iam/admin/capabilities`), made on demand by whoever IAM lets. A level policy is marked "level" on Policies and opens read-only with what it grants. "<W> access" (a workspace-owned "<label> access") is marked "workspace offer" and opens with the offer editor (`components/access/offer/`): the features (`/feature-access`, Everyone or Nobody) and the agents, apps, workflows and pipelines by module (`GET`/`PUT /api/workspaces/{id}/offer`; the modules are those `/publishers` lets the caller give there, a module's items listed on demand with `/resources`), as switches, saved in one write. Its Ontologies section lists every ontology file of the deployment (`ontologies` of `GET /offer`), one switch each saved at once (`PUT /api/workspaces/{id}/offer/ontologies`, as Settings › Ontologies writes it): a file the caller may not assign is read-only with its reason, a ref no file answers to stays removable. Built-ins (`components/access/builtins.ts`): "Platform member" / "Platform viewer" read "Platform access (automatic)" on a person and are never listed nor attachable; the service accounts' policies (`builtin.api|engine|job|idp|module_bootstrap`, `module.*`) are listed only under Platform › Service accounts, read-only. Platform settings › Models › Sets (`app/settings/models/`) reads the model sets from their platform policies (no endpoint of its own), with "Models · all" made on demand. Workspace creation picks the workspace admin (`admin_id`, the creator by default; the route's 400 about the admin, someone outside the organization's directory, shows at the picker, `adminRefusal`); no Owner is picked anywhere outside the people pages. The platform's "Platform admins" and "Workspace admins" (S2: whoever is in a "<W> admins" or "<O> admins") are listed first with the levels. "Superadmin" reads "Platform admin" wherever people read it (`lib/access-model/naming.test.ts`); internal names (`is_superadmin`) stay.
- **Policies**: the scope's own and those of other levels listed there (`listPolicies(after, scope)`: those it may attach from above; at the platform, every level's), as a tree: each sub-policy below its parent (`policyTree`; filtered, a flat list). A new one is owned by the scope (`createPolicy({ scope })`) and validated as such (`validatePolicy(source, scope)`). A policy is edited at its owner, wherever it is listed: the Owner column names it (`policy-owners.ownerLabel`, the containers named as the caller lists them, `resources` at each container) and links to the policy's page at its owner (`ownerHref`, `<owner's Policies>/<id>`) when the caller may manage something there (`access` at the owner). Whoever IAM lets `iam:UpdatePolicy` at the owner edits it from any page, the builder, the suggestions and the validation at the owner's scope, never the page's; for anyone else it is read-only, and the editor says who owns it and why, with the link. An open policy names its parent and its sub-policies (`getPolicy`), each a link that opens it. Deleting a parent that has sub-policies shows IAM's refusal at its row.
- **The policy builder** (`policies/builder/`): from `GET /publishers?scope=&parent=`, the publishers in IAM's order: Engine (the kernel services and `iam`), naas_abi (`nexus`: organizations, workspaces, members, features…), then the modules by key (their declared catalog, their agents, apps, workflows and pipelines). Each publisher opens and closes, its "N of M chosen" shown closed too; a builder of at most 12 types opens all of it, a larger one only the publishers with choices. A publisher with types of several services (the engine) groups them by service, the services by name, containers first in each (`serviceGroups`), each group under a heading that opens and closes. One search at the top filters the whole builder (`searchPublishers`: a publisher's id or label, a type's `service:type` and label, its actions' names, its module): what it finds opens (the types too, when at most 8), "Nothing matches" when nothing does, and clearing it restores what was open; choices made under a search stay. Under each, its resource types; under a type, its actions the caller may grant, as checkboxes; then its resources: the patterns the caller may grant it on ("all you may grant"), the existing ones from `GET /resources` (searched as typed, paged with Load more; a listed name is written `${scope}/…`, `scopedName`; only those a pattern the caller may grant of the type covers, Denies aside, `grantableOn`; the container itself listed as `${scope}`, shown once), or a wildcard typed after `${scope}/`, which must end with the type's step (`wildcardProblem`) and is checked with `POST /policies/validate` before it is added. A type with no lister (`listed: false`) is offered as patterns and wildcards. Each type's choice is one Allow (its actions in the type's order) with its own sid (the actions with their services, `TripleStoreQuery`, never one a kept statement has); a document reads back into choices, a type's first statement only, and what the builder cannot show stays as statements ("N other statements stay as written"). A new policy can start from a built-in role the caller's policy list holds; back to Nothing empties it. The statement editor and the YAML/JSON view are the advanced modes. IAM's refusal at save ("You cannot grant what you do not hold: … allows <action> on <resource> …") is shown beside the type whose choice it names (`refusedTypes`) as well as above.
- **Sub-policies.** A new policy may be a sub-policy of one listed at the scope ("Sub-policy of"; managed policies are roles to start from, not parents). The builder then reads `/publishers?parent=&derive=true`: what the caller holds there within the parent's chain (IAM's `grantable(parent=, derive=True)`), so it offers only what the parent has and the caller may grant, and a parent that creating the policy would refuse (not derivable, not the owner's, too deep, not found: 403/404/422) is refused there: its words show under the picker and Create is disabled. Any other failure (IAM unavailable, a chain it cannot read) is shown with Retry and blocks nothing: IAM judges the save. While a new parent is read the builder says it is loading. Choices left unfinished (actions without resources, or the reverse) stay across the reload as far as the type is still offered. An existing sub-policy is edited within its parent (`derive` off: reading the parent is enough).
- **The Statements view** suggests only what the caller may grant: the actions and types of the same `/publishers` answer (`grantableCatalogs`), the patterns they may grant the statement's actions on first (`grantablePatterns`), and the ids of the step being typed from `GET /resources` (`typedStep`; a module's items once `<module>/` is typed), each only where the listing names it (what was typed before the id is the listed resource's container, at `${scope}/` or written whole) and only when the caller may grant it (`grantableOn`, as the builder). Never every catalog, and not `/api/modules/scopes`. The simulator (platform only) still suggests from `/catalogs`.
- **No role brings a feature.** There are no role feature defaults to edit: a feature comes from a policy (a workspace's "Features of <role>", made once from the old defaults), attached from a policy's or a person's page. An invitation carries no policy: the people forms pick capability groups (`CapabilityGroupPicker`, `components/invitations/invite-policy-picker.tsx`, from `GET …/capability-groups`).
- **The people pages (#1589).** A person is a level (Member or Viewer, in all their workspaces, `LEVEL_EVERYWHERE_NOTE`), the workspaces they work in each with "admin", org admin or not, and capability groups; no role and no Owner is picked. Organization › Users › person edits all of it (`[userId]/member-access-editor.tsx`, saved as `PATCH …/members/{id}` with `org_admin`, `level`, `capabilities` and `PUT …/members/{id}/workspaces`); its "Remove from organization" (`DELETE …/members/{id}/access`) leaves every group of the organization and shows the API's 409 for the last org admin. Workspace › Users › Add and Create user pick the level, admin and capability groups. Platform › Users: Create user has "Platform admin"; a person's page opens on "Platform access (automatic)" (`platform-access.tsx`, `GET /api/admin/users/{IAM id}/access`, one request: the API finds the account, #1608), read-only.
- The client is `src/lib/iam-admin/` (`types.ts` is the contract, `api.ts` one function per route, `use-access.ts`). Gate a button with `can('iam:...')`, never a role name or a level; a row at another level than the page's, with `access` at that level (`policy-owners.useActionsAt`, asked once per level), and name containers with `useContainerNames`.
- Tests: jsdom render tests beside each view (`@/lib/testing/mount`), pure model tests (`builder-model.test.ts`: publisher order, types and actions, resources picked or a wildcard, statements written and read back, sub-policy narrowing), and `access-page.test.ts`, which renders every page at the three scopes for a platform admin (everything), an organization admin (organization and workspace Policies and Groups), a workspace admin (their workspace only), a delegated lister holding only `iam:ListPolicies` (exactly that), a policy builder holding only `iam:CreatePolicy` (Policies, no list), a holder of `iam:ListAttachments` (Policies) and a viewer and a stranger (nothing), and checks the menus agree. `policies.test.ts` checks that a user holding only agent A and `iam:CreatePolicy` is offered A alone, in the builder and in the Statements view. `people/person.test.ts` renders a person's page for each viewer as the API answers them (the platform admin: every level and the group; an organization's admin: inside the organization; a workspace's admin: what IAM lets them list; a member: nothing), and the role of an account linked from the old login (changed as its members name it, never one's own); `access-page.test.ts` opens that account on its page and from a group's members, and links a group only where Groups is shown; `access-paths.test.ts` the addresses and the old Roles & permissions redirects; `components/settings/settings-access.test.ts` which persona sees which page of Access at each level; `groups.test.ts` a group's page (opened by link even when the list fails), `policy-attachments.test.ts` where a policy is attached (an unattached one, Refresh asking again).

Decisions:

- **One UI, the scope a parameter.** Decision: Platform, Organization and Workspace settings mount the same `AccessPage`, given their scopes and the page; it asks `GET /access?scope=` and shows the page when an action of it is held. Consequences: no page or button is chosen by level; what only the platform administers is absent at an organization or a workspace because the API answers those actions false there (`iam_admin/AGENTS.md`). There is no Built-in roles section: no role brings a feature. System › Access, Organization settings › Access and Organization settings › Roles are gone, and the old per-level copies (`AttachmentsPanel`, the attachments browser) with them.
- **Policies are first-class; rights visibly come from them.** Decision: Roles & permissions is split into pages of their own, Policies first: Platform › Access (after Administration: Policies, Groups, Service accounts, Module approvals, Simulator, Audit), Organization › Access (Policies, Groups), and Workspace › Access (Policies, Groups) next to Members, each gated by the actions of its old section. The built-in roles (Owner, Admin, Member…) are listed with the policies, marked built-in and read-only; a policy's page opens on who holds it and at which scope. People & roles is gone: it duplicated Users, which now has each person's page (what they hold, at which scope, their groups, View as) and, for whoever may list who holds what and not the accounts, the holders. Consequences: an organization's or a workspace's Access shows only to holders of IAM rights at its scope (an owner or admin IAM gives none sees Members, not Policies); every capability of the old page has a page (a person's role changes on their page and on Members); no API permission changed and no route was added. Old addresses redirect (`oldAccessRedirect`, from `middleware.ts`): `/settings/roles?section=<s>[&policy=|&group=]` to that page (People & roles, `&person=`, to Users or the person), `/organizations/<org>/settings/roles?…` and `/workspace/<ws>/settings/permissions?…` (behind `/org/<slug>` too) to the level's Policies or Groups, People & roles to its Members.
- **A role is a membership, other policies are attachments.** Decision: a person's page and the Members pages change a person's built-in role through the membership routes (`changeMemberRole`); the attach form never offers a person `builtin.<role>`, a group or a service account any policy. Consequences: the org-wide mirror of an org owner or admin, the platform companions and owner protection follow a role changed here as from Members (`services/iam/AGENTS.md`, "Memberships change through `MEMBERSHIPS` only").
- **The builder offers what the caller may grant, by publisher.** Decision: the builder and the Statements view's suggestions are `GET /publishers` (IAM's `grantable` by publisher and type, within a sub-policy's parent) and `GET /resources` (as the caller), never the catalogs or the module listing. Consequences: it may offer less than IAM would take (a statement the builder cannot read as a type's choice stays writable in the Statements view), never more; a user holding only agent A sees A and nothing else anywhere in the editor; features are naas_abi's `feature` type, in its place among the publishers; a refusal is IAM's words beside the type.
- **One statement per type.** Decision: a type's choice (its actions on its resources) is one Allow; a second statement of the same type, a Deny, actions of several types or a wildcard action stays as written. Consequences: a policy written in the builder reopens with the same choices; a hand-written policy opens in the Statements view unless the builder shows all of it.
- **Narrowing to a parent is IAM's.** Decision: what a sub-policy may grant is asked of IAM (`grantable(scope, parent=)`), not intersected in the browser. Consequences: the builder of a sub-policy agrees with what IAM takes at save (`_require_held` with the chain), and a parent the caller may neither derive from nor read is refused before anything of it is shown.
- **One place for a principal's access, at every level.** Decision: a person's page, a group's page and a policy's attachments list what IAM's `list_attachments` (each attachment filtered by `iam:ListAttachments` on it) and `list_principal_groups` (each group by `iam:GetGroup`) return, across levels, from any page; Nexus filters nothing and checks no role, and each button asks `access` at its row's level. Consequences: from a workspace's page, a person's page reaches above the workspace only where IAM lets the caller list it; an organization's admin sees what is inside their organization, the platform admin everything, a member nothing; a policy's page shows who holds it at every level the caller may list, with the detach at each row's level.
- **The workspace's Access pages are `settings/policies` and `settings/groups`.** Decision: Platform Settings' are under `/settings/access/`, so the workspace's keep the short paths. Consequences: their bare legacy links (`/settings/policies`, `/settings/groups`, and the old `/settings/permissions`) go to the workspace like the other workspace settings links (`LEGACY_WORKSPACE_SETTINGS_SLUGS`), where `permissions` redirects to Policies.
- **General › Features is part of the workspace's offer.** Decision: Workspace settings › General › Features (`app/workspace/[workspaceId]/settings/general/feature-access*.ts(x)`, `GET` / `PUT /api/workspaces/{id}/feature-access`, `api/app/services/feature_access/AGENTS.md`) has one row per enabled feature: Everyone or Nobody, the feature in or out of "<W> access" (S3, #1586), written by the API as the caller; Only… is gone (an exception for some people is a group holding a policy). The same switches are in the offer editor on "<W> access"'s page. A row lists the other policies naming the feature (also granted or denied by, linked to their page; a Deny wins), says "not offered in this workspace" when the workspace's access policy does not allow it (linked to widen it), and is read-only when its policy was changed by hand or the API answers `editable` false; the browser checks no role. Several rows are saved in one `PUT`. Consequences: there is no feature switch outside IAM; Access › Policies marks those policies "managed from General" (`managed_from`), and one edited there turns its General row read-only; platform administrators still see every feature, whatever is chosen.

## Ontology catalog: in-engine and remote ontologies

`apps/api/app/services/ontology/` lists an ontology by its `path`, one opaque string the web app passes back on every call. It is either a file on disk (in-engine modules, from `module.ontologies`) or a **remote id** `module/<module_id>/<path relative to ontologies/>`, the key a remote module's file has in the engine's schema graph (`http://ontology.naas.ai/graph/schema`, an `internal:Schema` with base64 `internal:content`).

- `ontology_source.py` owns the remote side: `parse_remote_id` (rejects `..`, `.`, empty segments, backslashes, control characters), `RemoteOntologyReader` (reads the schema graph through the engine's triple store service; `files()` reads every remote text in one query for the listing, and each text is cached 30 s, at most 64 texts) and `load_remote_graph`. `_load_ontology_graph` and the import resolver (`ontology_imports.py`) dispatch on it: a `module/` path is **never opened as a file**, so a remote id cannot read the disk. An in-engine path that starts with `module/` is skipped.
- `list_ontology_files` adds the remote files with the in-engine filters (`owl:Ontology` required, `sandbox` and `processes` skipped); `module_name` is the remote module id, so a catalog ref `acme.reports:ReportsOntology.ttl` matches. A remote id matches a workspace allowlist only by its full id or `<module_id>:<file>` (`ontology_catalog_aliases`): never by the bare file name or a path suffix, which any module could reproduce and so enter a workspace that enabled another module's file. The listing runs off the event loop (`asyncio.to_thread`) and keeps each file's row per content version, so an unchanged file is not parsed again. An unreachable schema graph never hides the in-engine files.
- Export: `export_ontology` returns a file (in-engine) or the stored text (remote); the `/export` route answers either as an attachment. `process_slices` is empty for a remote file (its slice files stay in the module).
- A change a module pushes shows within the cache TTL (or at once after `POST /cache/clear`). Files a module later removes stay listed: nothing unloads them.
- Tests: `ontology_remote_test.py` (fake schema graph, listing, stats, export, traversal, cache bounds).

## Mobile list-detail pattern

Several NEXUS surfaces use the same mobile UX: a **list screen first**, then a **detail screen** with back navigation. Desktop keeps the two-column sidebar + content layout unchanged.

**Breakpoint:** `768px`, via `useIsMobile()` / `MOBILE_BREAKPOINT_PX` in `src/hooks/use-is-mobile.ts` (same threshold as Tailwind `md`).

### Contract

| Surface | List URL | Detail URL | List content | Detail content |
|---|---|---|---|---|
| Maps | `/workspace/{id}/maps` | `/workspace/{id}/maps/{datasetId}` | `MapsSection` (Public / Private; Custom when populated) | Dataset canvas (Public SA layers, presence) |
| Chat | `/workspace/{id}/chat` | `/workspace/{id}/chat/{id\|new}` | `ChatSection` (conversations) | Chat thread page |
| Settings (any level) | `/settings`, `/organizations/{orgId}/settings`, `/workspace/{id}/settings`, `/account` | The level's page | Header (back, Settings, Help and Log out icons), the tabs of the levels the caller opens (scrolling sideways), then `SettingsLevelsNav`: the active level's pages | Section page under the header (back, its title, Help and Log out icons), no tabs; back to the level's list URL |
| Account | `/account` | `/account/{section}` | Settings nav (`lib/nav.ts`) | Section page; the top bar's avatar opens the account menu (Account → `/account/profile`) |
| Files | `/workspace/{id}/files` | `/workspace/{id}/files/browse` | `FilesSection` (Drive and View pickers, search, Starred, then the views' tree) | File browser page |
| Org settings | `/organizations/{orgId}/settings` | `/organizations/{orgId}/settings/{section}` | Settings nav (`lib/nav.ts`) | Section page |
| Platform settings | `/settings` | `/settings/{general,organizations,users,roles,drives,system,activity,resources,data,tables}/...` | The Platform tab: every group of `settings/lib/nav.ts` with an item the caller holds | Item page; a table closes to Nexus tables |

**URL is the source of truth.** Each module exposes a small route parser:

- `src/app/workspace/[workspaceId]/maps/lib/maps-route.ts` → `parseMapsRoute`
- `src/app/workspace/[workspaceId]/chat/lib/chat-route.ts` → `parseChatRoute`
- `src/app/account/lib/account-route.ts` → `parseAccountRoute`
- `src/app/workspace/[workspaceId]/files/lib/files-route.ts` → `parseFilesRoute`
- `src/app/organizations/[orgId]/settings/lib/org-settings-route.ts` → `parseOrgSettingsRoute`

**Shell ownership:** On mobile, `workspace-layout.tsx` (workspace sections), `account/layout.tsx` (account), or `organizations/[orgId]/settings/layout.tsx` (org admin settings) decides list vs detail from the URL + `useIsMobile()`. List screens render the sidebar section component with `detailOnly` (workspace) or the module nav (account / org settings); detail screens render `{children}` and use back to the list URL.

**Immersive detail:** Bottom nav hides on detail views (chat thread, files browse). List screens show `MobileBottomNav`.

### Adding the pattern to a new sidebar section

1. Add `{section}-route.ts` with `is{Section}Route` and `isDetail` (or equivalent) parsed from the pathname.
2. In `workspace-layout.tsx`, mirror the chat/files blocks: `showMobile{Section}List`, `showMobile{Section}Detail`, render `{Section}Section detailOnly` on list.
3. Pick a detail slug or nested route (e.g. `/files/browse`); update section nav clicks on mobile to push the detail path via `useIsMobile()`.
4. Wire `MobileTopBar` back to the list URL; page `Header` registers the detail title via `useRegisterShellTitle`.
5. Add colocated vitest coverage for the route parser (see `chat/lib/chat-route.test.ts`, `account-route.test.ts`, `files/lib/files-route.test.ts`).

### Sections not yet on this pattern

| Section | Mobile today | Suggested detail route |
|---|---|---|
| Graph / Knowledge | Bottom nav → network view directly | `/graph` list → `/graph/network` (partial; graph has sub-views) |
| Apps | Bottom nav → apps grid | `/apps` list → `/apps/{slug}` |
| Ontology, Lab, Code, Search, Marketplace, Settings | More sheet only | Apply same list-first when promoted to primary mobile tabs |

## Testing and verification

Prefer colocated tests when changing domain behavior. Follow nearby file naming (`test_*.py` or `*_test.py`). Run the full gate before handing off substantial backend changes.

From `apps/nexus/`:

```bash
make check          # lint + typecheck + test (full gate)
make test-watch     # pytest --lf -x in apps/api/
```

Targeted checks:

```bash
cd apps/api && uv run pytest tests/ -v
cd apps/api && uv run mypy app/
cd apps/api && uv run ruff check app/
cd apps/web && pnpm typecheck
cd apps/web && pnpm test
```

**Web tests run on vitest only.** `pnpm test` runs every `src/**/*.test.ts` and is a pull request check (`nexus-web-tests` in `.github/workflows/pull_request.yml`), so it must stay green. Import `test`/`describe`/`it` from `vitest`, never from `node:test`: vitest finds no suite in a `node:test` file and the file fails. `node:assert/strict` is fine. A test that describes a behaviour not built yet is `it.skip` with a comment saying what is missing, not a failing test.

**Settings navigation baseline (#1603).** `apps/web/scripts/measure_settings.py` is an optional Python/Playwright browser tool, outside the product bundle. It measures Platform Groups, Organization General, Workspace Agents and Account Profile/Appearance: a fresh browser context, then a real Settings-link revisit after a detour. It observes unsaved input and scroll without clicking Save. From `apps/web`, against an already-running frontend:

```bash
python scripts/measure_settings.py --base-url http://127.0.0.1:3000 \
  --environment development --fixture --runs 3 --output /tmp/settings-before.json
python -m unittest discover -s scripts -p measure_settings_test.py
```

Use an existing Python environment with Playwright and Chromium installed. `--browser-executable` selects an existing Chromium when needed. The tool returns a sanitized `unavailable` report if the browser/dependency is missing; it does not install dependencies or start any service or migration. Fixture mode intercepts browser API calls with synthetic data (80 ms per call, five groups by default; both configurable) and is restricted to a loopback frontend. Intercepted browser requests never reach the real API; server-side rendering requests are outside the browser interception, so use a frontend configured for an isolated test environment. Its timings describe the frontend with a fixture, not backend/database or production performance. No response bodies, credentials, raw resource ids or query values are recorded; request equality is tracked with per-run keyed digests. Reports and authentication state stay outside git.

For an authenticated **test deployment**, omit `--fixture` and supply `--organization-id`, `--workspace-id` and a private existing Playwright `--storage-state` file. This mode blocks API writes except web-pass handshakes; Workspace Agents requires explicit `--allow-agent-sync` to permit its existing navigation-triggered reconciliation. Do not use that flag to benchmark production data. Missing access, navigation links, content markers and fixture endpoints produce partial/unavailable samples, not successful timings. Mark the actual server mode with `--environment production` only for a production build. The report records the local checkout revision, dirty state, browser/driver, samples and cache conditions: a fresh context does **not** clear server/build caches, and development compilation may dominate the first run. Request interception disables the browser HTTP cache in both modes; the revisit still retains the app's router/module state. Transfer sizes/Chromium JS heap are best-effort, not total process memory. Compare repeated runs with the same fixture size, delay, viewport and server mode, without running tests/builds concurrently. For a remote deployment, record its actual deployed revision alongside the report: the local checkout revision alone does not identify its server code.

**Settings API cache freshness (#1604).** `apps/api/app/services/settings_cache/middleware.py` reuses an already-authorized response only for the same verified session user, IdP group set, path/query and authoritative IAM revision. `IAMService.authorization_revision()` reads the store and refreshes local IAM caches even when a change notice was missed. Reads and fills are bracketed by fresh revision/invalidation-token checks; unavailable IAM/cache metadata falls through to the route and its existing guards. Restricted credentials and View as still bypass the response cache. IAM's current policy language reserves conditions rather than evaluating time-dependent conditions: introducing such conditions or another authorization input requires extending this cache contract or disabling response reuse.

Invalidations replace random tokens in the **cold tier**, never increment a possibly stale hot value. All API workers must share that authoritative cold backend for cross-worker data invalidation. Container/IAM writes remain global; narrower writes invalidate resource families (agent sync affects agents; provider changes also affect agents; secret changes also affect providers, agents and apps). The existing read-by-POST registry exempts validation, simulation, previews and app-link minting, but **not** agent sync: it still reconciles and invalidates agents. A failed Reload returns 503 instead of claiming it refreshed. Invalidation failures after a business write are logged without changing its response; IAM revision checks still prevent stale grants, but business-data freshness during a cache-write outage remains best effort. Deploy the change to every API worker and restart them; old workers still have the earlier authorization/invalidation behavior. No frontend dependency, security guard or database migration is removed or added.

JSON mutation responses are held until transaction cleanup and invalidation finish, so an immediate client re-read cannot run ahead of successful invalidation. Event streams and binary responses still pass through as they arrive. Query parameter order is preserved in keys: repeated parameters can select different workspaces when reversed.

Tests: `apps/api/app/services/settings_cache/middleware_test.py` covers SQLite revocations through the current service, a second service/connection and direct store changes, refiltering, credentials/groups, failures and in-flight invalidations. `libs/naas-abi-core/.../services/iam/IAMService_cache_test.py` covers the fresh revision capability. The browser benchmark above remains the frontend reference; fixtures do not measure this backend change's production latency.

**Shared permission reads (#1605).** `apps/web/src/lib/permission-cache.ts` is the single memory cache used by `authFetch` for scoped IAM access, analytics access and platform admin reads. Organization discovery opts its role-bearing list into it explicitly; ordinary resource reads remain live. Keep the existing Zustand hook interfaces and optimistic navigation. Default IAM API clients share the canonical HTTP entry; injected implementations are isolated by object identity. The cache binds responses to API/user/session generation and View as identity, shares in-flight requests, and rejects obsolete responses before sending or delivering them. A new session of the same user (another CSRF token) resets it; the first CSRF token of a page load does not, since it confirms the session a restored user already read with (the provider it adds is not part of the identity: a session at another provider brings a new token). Unknown or transitioning sessions do not cache. It never replaces backend guards.

Fresh entries live 60 seconds, denials 15 seconds and transient errors 2 seconds; stale mounts/focus revalidate, without a polling timer. Explicit Refresh bypasses settled entries; concurrent consumers still join one in-flight read. An observed grant or denial change clears sibling permissions and rejects their older in-flight replies; transient failures retain the last navigation while the backend continues checking every operation. IAM/membership/feature mutations, Reload, sign-out, API/session changes and View as transitions invalidate permissions. Validation, simulation and agent sync do not. The response cache is bounded to 128 entries and 256 KiB per body, with LRU eviction; cookies/streaming responses and requests with custom credentials, headers or abort signals bypass it. It uses neither persist middleware nor browser storage, and underlying permission fetches use `no-store`. `useIamAccess`, scoped owner actions and the existing platform/organization/analytics stores mask answers from older identities immediately. Events reuses the platform's `nexus:ReadSystem` answer; it must not imply superadmin access, which keeps `/api/admin/me`.

Tests: `lib/permission-cache.test.ts` (deduplication, TTL, bounded memory, failure and stale-generation races), `stores/auth-permissions.test.ts` (real hooks/transport, session/API/View as boundaries, persistence exclusion, Events versus superadmin), and existing permission/role journeys. Run `pnpm test` and `pnpm typecheck` from `apps/web`. The fixture browser benchmark measures frontend navigation/request counts; it does not measure real IAM/database or production latency.

**Shared resource reads (#1606).** `apps/web/src/lib/resource-cache.ts` keeps business answers that several Settings views read, in memory, under a policy each resource declares once (`defineResource`): its freshness, whether the API's settings cache may answer it (`backendCache`, passed to `authFetch(url, init, { settingsCache })`), and which successful changes make it stale (`invalidatedBy`, matched against the API path of every non-GET `authFetch`). A prefetch and a page read of one resource therefore follow the same policy; reads not declared yet still opt into the API's settings cache by the open page (`shouldUseSettingsCache`), until later batches declare them. Callers at the same time share one request; a fresh answer is served without one; a refusal (401/403/404) is kept 15 seconds at most; failures, non-JSON bodies, answers over 1 MiB and answers invalidated while in flight are never kept (the last are still delivered to their callers). Entries belong to the permission cache's session identity (API, user, provider, View as), once the API has confirmed the session of the page load (`configureResourceSession`: the auth store holds its CSRF token). A user restored from the browser's storage lacks the provider the session read adds, so nothing is kept before that read, and reads begun before it are answered as before, not kept: the read is not taken for another identity. A new identity, sign-out, every IAM change (`changesPermissions`) and Reload drop every entry, and an answer begun under another confirmed identity is rejected (`ResourceSessionChanged`), also after A→B→A. At most 64 entries and 4 MiB, least recently used first; no persist middleware or browser storage. Declared so far:

- `ORGANIZATION` and `ORGANIZATION_DOMAINS` (`lib/organization-resource.ts`, a minute): the Organization settings layout, General, Branding, Workspaces and the workspace shell's branding (`lib/org-branding.ts`) share one read; any change under `/api/organizations/<id>` or an `org-branding-updated` event drops them.
- `AGENT_ROSTER` (`stores/agents.ts`, 5 minutes): the agents store and an agent's settings page read one answer (`readAgentRoster`), and the reconciliation's own answer (`POST /api/agents/sync` returns the roster) primes it. Agent settings reconcile when the last reconciliation in this session identity is older than `SETTINGS_RECONCILE_MS` (5 minutes) or after Reload (`forgetAgentsSync`); the chat pane keeps once per session (`ensureAgentsSynced` without a bound). A reconciliation in flight is awaited, not sent again. Agent, provider and secret changes drop the roster; the store's own optimistic updates are unchanged. The Agents list no longer reads the workspace's servers, which it never showed.
- `PROVIDER_MODELS` and `AVAILABLE_PROVIDERS` (`stores/models.ts`, 5 minutes): the models store, Models settings (`ModelsPanel`) and the integrations store share each catalog; a provider or secret change drops them, and a model edited in Models settings calls `invalidateModelCatalog` (the persisted store's timestamp too).

The API stays the authority: nothing here decides access, and a cached answer is never used for a change. Tests: `lib/resource-cache.test.ts` (sharing, freshness, refusals and failures, unknown session, A→B→A, invalidation in flight, targeted invalidation, bounds, priming) and `stores/settings-resources.test.ts` (the real stores and `authFetch` over a fake API: Organization General's return without a request, Agents list/detail/store on one roster and when they reconcile, the catalogs' consumers, identity and IAM boundaries, the API settings cache by resource).

**Page state across navigation (#1607).** `apps/web/src/lib/page-state.ts` keeps how a Settings page was left, in memory, independently of its DOM, so a sidebar or cross-level round trip (and back/forward) finds it as it was; URLs and history are unchanged, and nothing is kept alive. An entry is keyed by scope (`account`, `organization:<id>`, `workspace:<id>`, `settings`), page and detail, and belongs to the permission cache's session identity (API, user, provider, View as) once the API has confirmed it (the #1606 resource cache's session: a restored user's session read, which adds its provider, is not another identity): a new identity, sign-out, an unknown session and a running view (the `nexus-view-as` flag) drop everything and keep nothing, also after A→B→A, and a page open when the identity changes starts afresh (`usePageState`), never showing another identity's state. Plain JSON data only, at most 96 entries, 64 KiB each and 1 MiB in all, least recently used first; no persist middleware or browser storage. Never kept: secrets, newly issued keys, payment inputs, tokens and View as data; those stay component state and go when the page is left. The hooks (`hooks/use-page-state.ts`): `usePageState(key, initial)` for filters, sort, tabs, selection and pagination (back to `initial`, nothing is kept); `usePageDraft(key, server)` for a form's non-sensitive edits, kept as a draft over the server snapshot it was made against (`rebaseDraft`): a fresh snapshot (another read, a background refresh of the user) updates the fields not edited and never the edited ones, and an edited field the server changed too is listed as a conflict until saved, discarded or undone (an editor with a revision, such as a policy, must keep the revision it began from in its draft, so the API's 409 conflict stays visible). Scroll is kept by path for the four layouts (`components/settings/settings-scroll-memory.ts`, in `SettingsLayoutRoot`): a return waits up to 3 seconds for the page to grow to the offset and yields to the user's own scrolling. Reload no longer remounts a page that reads again itself (`useSettingsReloadGeneration` in the effects that read); any other page under `SettingsReloadProvider` is still remounted. A branding update re-reads the organization and restyles the Organization settings layout in place (no `key` remount). Nexus tables' view (`app/settings/lib/tables-view.ts`) is reset when the identity changes (`onPageStateOwnerChange`). First batch: Account › Profile and Organization › General (drafts, conflict notice, Discard), Workspace › Agents (filters, the unsaved new agent, Reload in place). Not yet: Branding's form, the Agent/Skill/Policy/Search editors, other lists and analytics views; until then they keep component state (and the remount on Reload). Tests: `lib/page-state.test.ts` (keys, bounds, session/sign-out/View as, `rebaseDraft`), `hooks/use-page-state.test.ts`, `components/settings/settings-scroll-memory.test.ts`, `components/settings/settings-reload.test.ts`, `app/account/profile/profile.test.ts`, `organizations/[orgId]/settings/general/general.test.ts`, the branding case of `organizations/[orgId]/settings/layout.test.ts` and `app/settings/lib/tables-view.test.ts`. jsdom lays nothing out: real scroll restoration against Next's own scroll handling is checked in a browser (`scripts/measure_settings.py` observes scroll and unsaved input).

**Batched Settings reads (#1608).** A Settings list reads what it shows of many items in one request per bounded page, never one detail per item; each item inside a batch is authorized exactly as its per-item read (IAM's filter, as the caller), and nothing redacted is added. No route was added (extended ones keep the same `declares`, so the route matrix is unchanged), no migration, no permission changed.

- **Groups list** (`GET /api/iam/admin/groups?scope=&member_counts=true&limit=&after=`): each group's `member_count`, decided in one `filter("iam:GetGroup", …)` as `GET /groups/{id}` decides each, then IAM's `list_group_members`; `null` where the detail would be refused (a group listed only to attach to, or outside a view); no member is named. Pages are IAM's order with `next_after`; `limit` 1–500 (`GROUPS_PAGE_MAX`, 422 above), default IAM's 100 (the list used to stop silently at 100). Web: `listAllGroups` (`lib/iam-admin/batched.ts`) follows the pages; `groups.tsx` no longer reads a detail per group. At 500 groups (fixture test): 501 requests and 1,492 member-name lookups before, 1 request of 145 KB and none after (the list alone was 137 KB, the 500 details 554 KB).
- **A person's groups' attachments** (`GET /api/iam/admin/attachments?principal_id=a&principal_id=b…`, at most `MAX_PRINCIPALS_PER_READ` = 100, 422 above): each one's rows in the order named, as one request each would answer them (across levels, or at `scope` with the level's refusal rule over the batch); each policy and principal is named once. Web: `attachmentsByPrincipal` (chunks of 100, a failed chunk's groups each get their notice); `person.tsx` reads 3 requests whatever the number of groups (was 2 + one per group).
- **Platform › Users › a person** (`GET /api/admin/users/{id}/access`, `nexus:ListUsers` as before): `id` is the account's id or the IAM id (the row's `principal_id`, else IAM names the account linked from the old login; a deleted account is a 404, as it is not in the directory). `platform-access.tsx` reads it alone: 1 request instead of the whole `GET /api/admin/users` directory first.
- **Organization members** (`OrganizationService`): `list_workspace_memberships` reads every workspace's roles in one `MEMBERSHIPS.members_of` pass (was one `members` per workspace; `members_of` now names only the holders of the one organization when every scope asked is in it, as `org_directory` does, the answer at each scope unchanged), and `get_organization_member` (every member route's answer and a member's page) reads that member's account and profile alone, not every member's.

Not yet bounded (proposed follow-ups): Nexus tables (`core/platform_tables.py`: a `COUNT(*)` per table on the list, up to 5,000 unordered rows filtered in the browser; needs server-side pagination/filter/sort with a separate full-export path), the Platform and Organization Users lists and Organization Workspaces (whole directories, client-side filtering), the Access holders list (`people.tsx`, one group detail per holding group), and a person's role targets (`person.tsx` `memberAt`, a scope's whole member list to find one person). Tests: `iam_admin/adapters/primary/iam_admin__primary_adapter__FastAPI_batched_reads_test.py` (counts equal the details per viewer and scope, none where refused or outside a view, 500 groups paged, batches equal one-by-one per viewer, bounds, name lookups counted), `accounts__primary_adapter__FastAPI_test.py` (access by IAM id, deleted account), `organizations/service_test.py` (60 workspaces in one pass equal to one read each, another organization's holders not named, one member read alone), web `lib/iam-admin/batched.test.ts` (request counts and URLs through the real client), `groups.test.ts`, `person.test.ts`, `platform-access.test.ts`.

**Settings loading and runtime lifecycle (#1609).** A Settings page loads the code it shows, and what it leaves stops. *Splits* (`next/dynamic`, besides the System views and the explorer that already loaded on open): each page of Access loads its own view (`components/access/access-page.tsx`: Policies, Groups, Service accounts, Module approvals, Simulator, Audit); Analytics keeps Overview and its small tabs in the page and loads Chats and one user's detail on open (`components/analytics/analytics-section.tsx`; the other tabs are under 1 kB compressed, where a chunk costs more than it saves); a service page loads its own `ServiceView` and stylesheet (`data/services/registry.ts`: `loadServiceView`, `useServiceView`, one import per service, the registry itself imported beside the explorer), while the sidebar and Recent changes name and draw a service from `lib/nav.ts`/`lib/service-pages.ts` without its view; a view whose code fails to load says so and never falls back to the generic view (which would not mask a secret). Measured with `pnpm build` (gzip): platform Access pages 186 → 151 kB first load, organization Access 177 → 142 kB, workspace Access and a user's page 203 → 173 kB; analytics 153 → 148 kB; the explorer import 97.9 → 82.0 kB plus 1–11 kB for the open service. Every route pays about +1 kB (webpack's runtime lists the new chunks). *Prefetch*: the Settings column's links prefetch on intent (pointer, focus, touch: `SettingsNavItem`, `prefetch={false}` plus `router.prefetch`), never every link of the column in view. A route prefetch loads code and the route's payload and runs no effect; no data prefetch exists, and any later one must use declared safe reads (`defineResource`) and never agent reconciliation (`ensureAgentsSynced`, `POST /api/agents/sync`), secret reveals, key creation, streams or mutations. *Polling*: System views read through `usePoll` (`useSystemResource`): one call at a time, the next `intervalMs` after the previous settles, none while hidden or closed; Refresh or another path aborts the pending call (`loadSystem(path, fetcher, signal)`) and its answer, or one for another path, is never shown. The Events tail (`stores/events.ts`, shared by the feed and the graph) is single-flight too: a timer after each settled read, none while paused, hidden or without a viewer (the last unsubscribe clears the timer and aborts the read; the rows stay for the return); a filter change, Clear or a new identity aborts the read in flight and drops its answer. *Bounds*: the Events id set holds the ids of the rows held and no other (trimmed rows are forgotten; at most `MAX_EVENTS` from the live tail, Load older can add more until the next live rows trim them); the service views loaded are at most one per service. *GPU*: Layers releases its WebGL context on leave (`forceContextLoss` after disposing geometries, materials and textures); the Events graph schedules no frame after dispose. The Jobs failure badge (`useJobFailures` in the Platform layout, one poll a minute shared with the Jobs page) and the shared Events feed are kept. Tests: `system/system-resource.test.ts` (no overlap, closed view, stale Refresh and path), `stores/events-lifecycle.test.ts` (no overlap, paused/hidden/unwatched, aborted filters, bounded ids), `components/access/access-page-split.test.ts` and the first test of `analytics-section.test.ts` (which modules a page evaluates), `data/explorer.test.ts` (loading, then the view; others unloaded), `components/settings/settings-nav-prefetch.test.ts`. Remaining limits: the Layers scene still renders every frame while open (browsers pause it in a hidden tab); System views keep their last answer in component state for the life of the page; a route prefetch on intent still loads that page's code; Maps' image URL cache (`use-authed-image-url.ts`) is outside Settings and unbounded; the browser benchmark (#1603) was not rerun for this change.

## Conventional commits

NEXUS uses Conventional Commits enforced via `CONTRIBUTING.md` (`feat:`, `fix:`, `docs:`, `refactor:`, and so on). Consistent prefixes make cherry-picks and release notes tractable when syncing with upstream ABI. Match the style of recent commits when authoring messages.


## Sheets UI and agent

The Sheets editor uses `apps/web/src/components/sheets/workbook-grid.tsx`, a
virtualized native grid. `workbook-model.ts` reads/writes the JSON block in
`workbook.html`. Do not restore the fixed 1280×720 slide preview as the editor.
Sparse `column_widths` and `row_heights` persist pixel dimensions per tab and
are preserved by duplication and XLSX export. Formula entry supports arrow-key
and mouse cell references without moving the destination cell.
Row/column headers are editor chrome; row 1 remains workbook data. Bottom tabs
select sheets; direct edits, clipboard changes and tab changes autosave through
the existing workbook endpoint. Keep raw formulas intact in stored HTML/XLSX.

`POST /api/sheets/evaluate` validates workspace access and calculates a local
draft without saving. Both the grid and SheetsAgent use `sheets/formulas.py`.
`agents/SheetsAgent.py` loads `agents/sheets/skills/nexus-sheets/SKILL.md`.
`update_sheets_cells` performs bounded A1 edits without replacing other cells.
Include `naas_abi SheetsAgent` in explicitly restricted workspace agent rosters.

Focused checks from web: `pnpm test -- workbook-grid.test.ts workbook-model.test.ts sheets-`
and `pnpm typecheck`. Backend: run pytest on `apps/nexus/sheets/`,
`agents/SheetsAgent_test.py`, and the sheets primary adapter tests. The skill's
validation script checks HTML workbooks without mutating formulas.

Sheets mutations require writer membership. Saves use the existing source-control
upsert operations, as Slides does. Git is authoritative; sidecars are mirrors.
Dev output is `.next-dev`, separate from the production `.next` build directory.
