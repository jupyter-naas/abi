---
sidebar_position: 1
title: "Default Workspace Routing"
---

# Default Workspace Routing

- **Document Type:** ADR
- **Status:** Accepted
- **Date:** 2026-05-13
- **PR:** [#948](https://github.com/jupyter-naas/abi/pull/948)

## Context

The Next.js middleware must route the root path (`/`) and legacy bare routes such as `/chat` and `/search` to a workspace-scoped URL of the form `/workspace/<id>/chat`. Before this change, the middleware contained a hardcoded fallback slug `workspace-nexus`. This created two problems:

1. Any deployment without a workspace named `workspace-nexus` would land on a 404 after login.
2. There was no documented or configurable way to override the default without editing source code.

## Decision

Workspace routing now uses a three-tier resolution in the middleware:

1. **`nexus-last-workspace` cookie** - Set whenever a user visits any workspace page. Takes priority on every subsequent request. No configuration required.
2. **`DEFAULT_WORKSPACE` environment variable** - Read server-side at runtime (no `NEXT_PUBLIC_` prefix, so it is never exposed to the browser). Configured via `NEXUS_DEFAULT_WORKSPACE` in `.env`, which `docker-compose.yml` maps through to the container.
3. **Hard fallback `primary`** - Used only when neither the cookie nor the env var is present. Matches the default workspace slug seeded for local development in `config.local.yaml`.

The login action in `stores/auth.ts` was also updated to fetch the user's first workspace from `/api/workspaces` immediately after authentication and redirect directly to `/workspace/<real-id>/chat`, bypassing middleware resolution entirely on the happy path.

## Consequences

**Production deployments must set `NEXUS_DEFAULT_WORKSPACE`** to the slug of their default workspace. Without it, the fallback is `primary`, which produces a 404 on any deployment whose workspace slug differs.

The cookie-first approach keeps the risk window narrow: it only applies to a user's very first request or after the 30-day cookie expires. Once a user has visited any workspace, routing is automatic.

Local development is unaffected: `config.local.yaml` seeds a workspace with slug `primary`, matching the fallback.
