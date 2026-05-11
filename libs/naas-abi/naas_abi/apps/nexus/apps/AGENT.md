# CLAUDE.md — `libs/naas-abi/naas_abi/apps/nexus/apps`

Scoped instructions for working in the **Nexus frontend workspace**. Loaded automatically when Claude touches files in this directory or any sub-app (`web`, etc.). The repo-root `AGENTS.md` (linked as `CLAUDE.md`) holds the global conventions — read that first.

## Focus

Primary work area: `libs/naas-abi/naas_abi/apps/nexus/`
- **Frontend (priority):** `apps/web` — Next.js app, pnpm
- **Backend (secondary):** `libs/naas-abi-core/naas_abi_core/apps/api` — Python FastAPI

I work on this codebase regularly. Skip basic explanations. Be direct.
When I ask for a change, propose the diff and the reasoning — don't lecture.

## Repo layout (what matters)

- `libs/naas-abi/naas_abi/apps/nexus/apps/web` — frontend I'm working on
- `libs/naas-abi-core/naas_abi_core/apps/api/api.py` — REST API entrypoint
- `libs/naas-abi-core/naas_abi_core/engine/` — agent engine, module loading
- `config.yaml` — module + service config (gitignored, copy from `config.yaml.example`)
- `.env` — secrets and host config (gitignored)
- `Makefile` — automation entrypoint, look here before inventing commands
- `docker-compose.yml` — postgres, fuseki, qdrant, minio, rabbitmq

## What lives here

This is the Nexus UI workspace — a **pnpm monorepo of Next.js apps** that ships with ABI. The flagship app is `web/` (the chat/knowledge-graph UI on port 3000, talking to the Nexus API on 9879 and the Agent API on 8001). Sibling apps may exist under this `apps/` directory; treat each as a self-contained Next.js project with its own `package.json`.

This is the **only TypeScript/Node area in the repo**. Everything else is Python. Don't reach across the boundary in either direction.

## Layout you should respect

```
nexus/apps/
├── web/                     # Main Next.js app (port 3000)
│   ├── app/                 # Next.js App Router (routes, layouts, server components)
│   ├── components/          # Reusable React components
│   ├── lib/                 # Client/server utilities, API clients
│   ├── public/              # Static assets
│   ├── styles/              # Global CSS / Tailwind entry
│   ├── package.json
│   ├── next.config.{js,ts}
│   └── tsconfig.json
└── <other-apps>/            # Same shape if present
```

If you find a layout that doesn't match this, follow what's there — don't restructure as a side effect of an unrelated change.

## Hard rules in this workspace

- **Use `pnpm`. Never `npm` or `yarn`.** The lockfile is `pnpm-lock.yaml` and the workspace uses pnpm protocols. Mixing managers will desync the lockfile and break installs across the team.
- **Run commands from the right directory.** Frontend commands run from inside the relevant app (`apps/web`), not from the repo root. The repo-root `Makefile` doesn't proxy `pnpm` commands.
- **Don't edit `pnpm-lock.yaml` by hand.** Add/remove deps via `pnpm add` / `pnpm remove` so the lockfile stays consistent.
- **API contract is owned by Python.** The REST API (port 9879) and Agent API (port 8001) are defined in `naas-abi-core`. If you need a new endpoint, add it on the Python side first, then consume it here. Don't define API shapes in TypeScript and expect the backend to follow.
- **Localhost vs Docker hostnames.** Local dev hits `http://localhost:9879` for the API. The Python `.env` uses `localhost` (not `postgres`/`qdrant`/`minio`) — this is the same convention; don't hardcode Docker service names in frontend env vars.
- **Server vs client components matter.** Default to Server Components in the App Router. Add `"use client"` only when you need browser-only APIs, hooks with state, or event handlers. Don't sprinkle it at the top of every file "just in case" — it forfeits streaming and bloats the client bundle.
- **No secrets in `NEXT_PUBLIC_*` env vars.** Anything `NEXT_PUBLIC_*` is shipped to the browser. API keys, tokens, and internal URLs go in server-only env vars and are accessed from Server Components, Route Handlers, or Server Actions.

## Commands you'll run

From inside `apps/web` (or whichever sub-app you're in):

```bash
# Install (first time, or after pulling lockfile changes)
pnpm install

# Dev server (port 3000)
pnpm dev

# Production build + run
pnpm build
pnpm start

# Lint / type-check / format — names depend on package.json scripts;
# check `package.json` "scripts" before assuming.
pnpm lint
pnpm typecheck   # if defined; otherwise: pnpm exec tsc --noEmit
pnpm format      # if defined
```

Before assuming a script exists, open the app's `package.json` and read the `scripts` block. Don't invent commands.

For the full local stack (frontend + API + infra), the repo-root commands still apply:

```bash
# From repo root
docker compose up -d postgres fuseki rabbitmq   # infra
uv run abi stack start                          # everything
uv run abi stack logs web                       # frontend logs only
```

## Adding a dependency

```bash
# Inside the specific app (e.g. apps/web)
pnpm add <pkg>            # runtime dep
pnpm add -D <pkg>         # dev dep
pnpm add <pkg>@<version>  # pin a specific version
```

Pin runtime deps to exact versions when stability matters (matches the project's general practice of deterministic builds). Commit the resulting `pnpm-lock.yaml` change in the same commit as the `package.json` change.

## Working with the App Router (if `web/` uses it)

- **Routes live in `app/`**, not `pages/`. A folder = a route segment; `page.tsx` = the route's UI; `layout.tsx` = shared shell; `route.ts` = a Route Handler (REST endpoint).
- **Data fetching belongs in Server Components** by default. Use `fetch()` with explicit `cache` / `next.revalidate` options — don't rely on default caching changing between Next.js versions.
- **Server Actions for mutations.** Prefer them over hand-rolled `/api/*` routes when the action is invoked from this app's own UI. Keep auth/validation inside the action; never trust client input.
- **Streaming + Suspense.** When a section of a page can render before slow data arrives, wrap the slow part in `<Suspense fallback={...}>`. This is one of the main wins of the App Router — use it.

## Styling

If the app uses **Tailwind** (likely, given the create-next-app default): keep utility classes inline in JSX, extract to components when patterns repeat 3+ times, and put truly global CSS in `app/globals.css` (or equivalent). Don't introduce a second CSS-in-JS library alongside Tailwind without a strong reason — it bloats the bundle and fragments the styling story.

Check `tailwind.config.{js,ts}` and `postcss.config.*` to see what's actually configured before adding plugins.

## Talking to the ABI backend

- **Nexus API** (port 9879) — platform endpoints (auth, modules, config). Authenticated with a Bearer token (`ABI_API_KEY` on the server side).
- **Agent API** (port 8001) — agent execution and streaming completions (SSE `data: {...}` chunks: `token`, `end`, etc.).
- **MCP** is a separate channel, served by the core Python app for external clients (Claude Desktop, VS Code) — it's not consumed by this frontend, don't try to wire it in.

For streaming responses, use the browser's native `ReadableStream` / `EventSource` patterns. Don't pull in a heavy SSE client unless you actually need its features.

## Things to refuse / push back on

- Switching to `npm` or `yarn` "because it's faster on my machine." It will break everyone else.
- Adding a UI library that overlaps with what's already installed (multiple icon sets, multiple component kits, multiple CSS frameworks).
- Hardcoding `http://localhost:9879` in committed code — read it from an env var so prod/staging can override.
- Putting business logic in components. Push it into `lib/` as plain functions that are easy to test.
- "Use client" everywhere. If you find yourself adding it to a layout or a top-level page, stop and reconsider what actually needs to be client-side.
- Editing the Python backend from this directory. If a backend change is needed, switch to the relevant Python package — its own `CLAUDE.md` will load.