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

**Why `workspace_id` everywhere:** multi-tenant isolation is a security invariant, not optional filtering. New tables and endpoints must filter by `workspace_id` and check workspace membership via the IAM service (`services/iam/`, see `IAM_SPEC.md` and `authorization.py`).

Do not add a second role check at the endpoint when the IAM service already does it. Duplicate checks are explicitly called out as anti-patterns in the migration doc.

### Business workspace vs Code workspace

These are distinct mental models. Do not conflate them in UI copy.

| | **Business workspace** | **Code workspace** |
|---|---|---|
| Audience | Analysts, managers, operators | Engineers |
| Role | Collaboration, reporting, assets, workflows | SCM, multi-repo, env, debugging |
| Lifetime | Long-lived | Often ephemeral |
| Auth / access | Org RBAC | Repo tokens / SSH; tied to branches, folders, containers |

Footer labels must say **Business workspace** and **Code workspace**. Canonical UX note (Zen): `docs/ux/business-vs-code-workspace.md`.

### Platform status footer

`WorkspaceLayout` always mounts `apps/web/src/components/shell/platform-status-footer.tsx` (desktop + mobile): **User / Business workspace / Repo / Branch / Code workspace** (+ **Saved** / **Unsaved changes** when relevant) on the left; **Refresh + API** on the right. Code workspace label links to the Coder dashboard URL from runtime binding (`https://coder…/@owner/name`) when available. Navbar must not show a fake branch selector or duplicate API chip. Slides registers Refresh via `SlidesStatusBar` (null render; no second footer) and publishes `deckDirty` / `coderUiUrl` through `stores/slides.ts`. Code syncs repo/branch/Coder through `stores/code.ts` and `stores/platform-status.ts`.

## Frontend

Next.js 14 App Router under `apps/web/`. State is Zustand (`src/stores/*.ts`, one store per domain: `auth`, `workspace`, `agents`, and others).

**Why `/api/tenant` at SSR:** tenant branding (tab title, OG image, theme) must be correct before first paint. `layout.tsx` fetches branding server-side. Do not bypass this API; it returns safe defaults on failure so white-label tenants never render a broken unbranded shell.

Cloudflare Pages deploy: `pnpm build:cf` then `wrangler pages deploy` (see `apps/web/package.json`, `wrangler.toml`). Standard `pnpm dev` runs Next.js on port 3000.

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

This yields reviewable diffs, cherry-pick friendly commits to upstream ABI (`integrate/zen-july` unpacks into small PRs to jupyter-naas/abi main), and clear ownership: routing vs component vs CSS.

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

Org-specific border radius comes from the org `loginBorderRadius` field and is exposed as `--org-border-radius`. Layouts set `data-org-branded="true"` on the branded subtree. Avatars always use `9999px` border radius and are excluded from org radius overrides.

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
    ├── workspaces/
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
| List workspace members | `GET /api/workspaces/{id}/members` | Workspace member |
| Invite workspace member (create-on-invite) | `POST /api/workspaces/{id}/members/invite` `{email, role, name?}` | Workspace owner/admin |

Notes:

- Invite **creates** the user when missing, adds membership, and emails OTP / magic-link sign-in (same challenge as `/api/auth/magic-link/request`). Optional `workspace_id` on org invite also adds workspace membership.
- UI must hide or disable Add / Invite for non-admins; API still returns `403`.
- **Agents:** `invite_organization_member` / `invite_workspace_member` in `naas_abi/agents/tools/nexus_admin_tools.py` use the same create-on-invite path in-process.

Web entry points: `organizations/[orgId]/settings/users/`, workspace `organization/users/`, workspace `settings/members/`. Store: `stores/organization.ts`.

## Maps UI module

Maps is a **dataset loader**, not the Knowledge Graph. Graph stays under `/graph` (ontology network). Maps sits first in the primary nav (before Search) and loads datasets onto a canvas.

**Ownership rule:** Nexus Maps owns situation-awareness Public layers as first-class product code under `apps/web/src/app/workspace/[workspaceId]/maps/` plus Maps API proxies under `apps/web/src/app/api/maps/`. Do **not** import from `naas_abi_marketplace/.../wsr`. World Situation Room is a legacy marketplace demo; do not couple Maps to it.

The Maps sidebar mirrors Search sources: collapsible **Public / Private / Custom** groups with `active/total` counts, icon + label rows, and `org-border-radius` via `maps-*` CSS. Empty buckets (including Custom upstream) are hidden. Maps in ABI is generic: product-specific datasets (for example Zen World Organization Graph) are registered by the deployment through the Custom bucket contract below, never hard-coded into upstream ABI.

| Bucket | Dataset | Route | Role |
|---|---|---|---|
| Public | OpenStreetMap | `/maps/openstreetmap` | Free OSM/CARTO basemap |
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
| Public | Flights | `/maps/flights` | airplanes.live sample tiles via `/api/maps/flights` |
| Public | Conflict Sites | `/maps/conflict` | Curated static OSINT pins in `maps/lib/conflict-sites.ts` |
| Public | Gulf Strikes | `/maps/gulf-strikes` | Live Gulf / Iran / Israel strike RSS geopins via `/api/maps/gulf-strikes` |
| Public | News | `/maps/news` | RSS proxy → light region geocode pins |
| Public | AIS Vessels | `/maps/ais` | Reserved; honest empty state until a free/licensed feed |
| Public | ISS | `/maps/iss` | open-notify ISS position (bonus thin orbit pin) |
| Private | **Here** (presence) | `/maps/presence` | User map: laptop / this device, optional iPhone pin, GCP `abi-naas-app` |
| Custom | *(empty upstream)* | `/maps/{id}` | Registered per deployment via `NEXT_PUBLIC_MAPS_CUSTOM_DATASETS`; do not ship product-specific datasets here |

**Custom bucket contract.** Upstream ABI ships the mechanism, never a particular layer. A deployment registers its own by setting `NEXT_PUBLIC_MAPS_CUSTOM_DATASETS` to a JSON array of descriptors (`src/lib/maps-custom-datasets.ts`), so a Custom layer only appears where an operator has pointed it at a backend that exists:

```json
[{ "id": "acme-sites", "title": "Acme Sites", "description": "Sites Acme operates.",
   "icon": "MapPin", "order": 0, "endpoint": "/api/acme/sites" }]
```

Every registered layer renders through `MapsCustomFeed` and fetches through the authed proxy at `/api/maps/custom/[datasetId]`, which requires a Bearer token plus `workspace_id` and is never cached. `endpoint` must be a **path on the Nexus API**: the proxy forwards the caller's token, so absolute and protocol-relative URLs are rejected at parse time, as are ids that are not route-safe and ids that shadow a built-in dataset.

Shared Leaflet bootstrap: `maps/lib/leaflet-map.ts` + `maps-feed-canvas.tsx`. CORS / User-Agent proxies live only under `/api/maps/*` (Maps-owned). FIRMS VIIRS WMS is proxied at `/api/maps/firms` only when `FIRMS_MAP_KEY` (or `NEXT_PUBLIC_FIRMS_MAP_KEY`) is set; without a key the Wildfires canvas is EONET-only (never ship a keyless/placeholder FIRMS WMS URL). OpenWeather temp tiles are not used (keys required).

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

Sidebar expand state: `stores/maps.ts` (`nexus-maps` persist). Feature flag: `maps` (enabled by default for owner/admin/member/viewer baselines). Mobile: `/maps` = library list, `/maps/{id}` = canvas detail. Maps is first in the workspace sidebar (before Search); app landing (middleware `/`, login, workspace switch) remains Chat (`/chat`).

## Files UI module

The workspace files surface is a self-contained module under `apps/web/src/app/workspace/[workspaceId]/files/`. Mobile chrome and desktop browse chrome (toolbar, table, grid, pagination) use semantic CSS in colocated route and component styles.

### Structure

```
src/app/workspace/[workspaceId]/files/
├── page.tsx                      # Desktop browser (re-exports browse)
├── lib/
│   ├── files-route.ts            # parseFilesRoute, filesBrowsePath (mobile list-detail)
│   ├── files-route.test.ts
│   └── drive-label.ts            # Drive root, label, breadcrumb helpers
├── components/
│   ├── files-components.css      # Shared mobile chrome styles
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
| `FilesMobileToolbar` | Add, refresh, view mode, search (mobile) | `browse.tsx` |
| `FilesMobileRow` | OneDrive-style list row | `browse.tsx` |
| `FilesAddSheet` | Bottom sheet for create/upload actions | `browse.tsx` |

Route parsing lives in `lib/files-route.ts` and is imported by `workspace-layout.tsx` and `files-section.tsx`.

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

## Mobile list-detail pattern

Several NEXUS surfaces use the same mobile UX: a **list screen first**, then a **detail screen** with back navigation. Desktop keeps the two-column sidebar + content layout unchanged.

**Breakpoint:** `768px`, via `useIsMobile()` / `MOBILE_BREAKPOINT_PX` in `src/hooks/use-is-mobile.ts` (same threshold as Tailwind `md`).

### Contract

| Surface | List URL | Detail URL | List content | Detail content |
|---|---|---|---|---|
| Maps | `/workspace/{id}/maps` | `/workspace/{id}/maps/{datasetId}` | `MapsSection` (Public / Private; Custom when populated) | Dataset canvas (Public SA layers, presence) |
| Chat | `/workspace/{id}/chat` | `/workspace/{id}/chat/{id\|new}` | `ChatSection` (conversations) | Chat thread page |
| Account | `/account` | `/account/{section}` | Settings nav (`lib/nav.ts`) | Section page |
| Files | `/workspace/{id}/files` | `/workspace/{id}/files/browse` | `FilesSection` (drives, starred) | File browser page |
| Org settings | `/organizations/{orgId}/settings` | `/organizations/{orgId}/settings/{section}` | Settings nav (`lib/nav.ts`) | Section page |

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
```

## Conventional commits

NEXUS uses Conventional Commits enforced via `CONTRIBUTING.md` (`feat:`, `fix:`, `docs:`, `refactor:`, and so on). Consistent prefixes make cherry-picks and release notes tractable when syncing with upstream ABI. Match the style of recent commits when authoring messages.
