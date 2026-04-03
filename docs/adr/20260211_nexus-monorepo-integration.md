# ADR: Nexus App Integration into the ABI Monorepo

- Status: Accepted
- Date: 2026-02-11

## Context

The Nexus frontend (Next.js) and its API (FastAPI) were maintained in a separate repository. This created friction: coordinating releases between the ABI Python monorepo and the Nexus repo required manual version pinning, delayed integration testing, and made it hard to ship full-stack features atomically.

## Decision

Integrate the Nexus app (both the Next.js web frontend and its FastAPI API layer) directly into the ABI monorepo at `libs/naas-abi/naas_abi/apps/nexus/`.

The Nexus API is wired into the ABI engine as a module: it receives the engine's configured services (TripleStore, VectorStore, BusService, etc.) at startup, rather than bootstrapping its own service instances. The Next.js frontend lives at `apps/web/` and is managed with `pnpm`.

The Nexus FastAPI app is mounted on the same process as the ABI core API, sharing the app instance and middleware (including CORS - see `20260305_cors-single-source-of-truth`).

## Consequences

### Positive
- Full-stack features can be shipped in a single PR with atomic version bumps.
- Integration tests cover the full ABI+Nexus surface in CI.
- Eliminates cross-repo version drift.

### Tradeoffs
- The monorepo grows in scope; developers need both Python (`uv`) and Node (`pnpm`) toolchains.
- The Nexus web app's `node_modules` adds significant disk usage and `pnpm install` is required in setup.
- Shared process means a crash or misconfiguration in Nexus can affect the core API and vice versa.
