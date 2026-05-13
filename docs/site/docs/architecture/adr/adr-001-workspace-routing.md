---
sidebar_position: 1
title: "ADR-001: Default workspace routing"
---

# ADR-001: Default workspace routing

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-05-13 |
| PR | [#948](https://github.com/jupyter-naas/abi/pull/948) |

---

## Context

The Next.js middleware must route the root path (`/`) and legacy bare routes (e.g. `/chat`, `/search`) to a workspace-scoped URL of the form `/workspace/<id>/chat`. Before PR #948, the middleware contained a hardcoded fallback slug `workspace-nexus`. This worked for the original deployment but created two problems:

1. Any new deployment that did not have a workspace named `workspace-nexus` would land on a 404 after login.
2. There was no documented way to change the default without editing source code.

## Decision

Workspace routing now uses a three-tier resolution in the middleware:

1. **`nexus-last-workspace` cookie** - Set whenever a user visits any workspace page. Takes priority on every request after the first. No configuration required.
2. **`DEFAULT_WORKSPACE` environment variable** - Read server-side at runtime (no `NEXT_PUBLIC_` prefix, so it is never exposed to the browser). Set via `NEXUS_DEFAULT_WORKSPACE` in `.env`, which `docker-compose.yml` maps through to the container.
3. **Hard fallback `primary`** - Used only when neither of the above is present. Matches the default workspace slug seeded for local development in `config.local.yaml`.

The login action in `stores/auth.ts` was also updated to fetch the user's first workspace from `/api/workspaces` immediately after authentication and redirect directly to `/workspace/<real-id>/chat`, bypassing the middleware resolution entirely on the happy path.

## Consequences

**Production deployments must set `NEXUS_DEFAULT_WORKSPACE`** (or its container equivalent `DEFAULT_WORKSPACE`) to the slug of their default workspace. Without this, the fallback is `primary`, which will produce a 404 on any deployment whose workspace slug differs.

The cookie-first approach means the risk window is narrow: it only applies to a user's very first request, or after the cookie expires (30-day TTL). Once a user has visited any workspace, the cookie handles routing automatically.

Local development is unaffected: `config.local.yaml` seeds a workspace with slug `primary`, matching the fallback.

## Alternatives considered

**Single hardcoded slug**: Simple but requires source changes for every new deployment.

**Redirect to workspace picker**: Cleaner UX for multi-workspace setups, but adds friction for single-workspace deployments that make up the majority of ABI installs.

**Read slug from API on every middleware request**: Correct but adds backend latency to every unauthenticated request and breaks the edge runtime constraint on Next.js middleware.
