# ADR: Nexus API Refactor to Hexagonal Architecture with ServiceRegistry

- Status: Accepted
- Date: 2026-03-30

## Context

The Nexus API (FastAPI) had grown endpoint-heavy: route handlers contained business logic directly, Postgres sessions were created ad hoc per route, and there was no consistent way to inject or replace service implementations. This made the codebase hard to test, extend, and maintain as the number of domains (auth, chat, workspaces, organizations, IAM) grew.

## Decision

Refactor the Nexus API toward hexagonal architecture using two cross-cutting infrastructure components:

1. **`ServiceRegistry`** — a centralized bootstrap registry that instantiates and wires all domain services at application startup. Route handlers receive services via dependency injection rather than constructing them inline.

2. **`PostgresSessionRegistry`** — a request-scoped session resolver that provides a single Postgres session per request lifecycle, preventing session leaks and simplifying transaction management.

Domain logic is moved into dedicated service handlers under `app/services/<domain>/`, each following the ports-and-adapters structure:
- `adapters/primary/` — FastAPI route handlers (thin, no business logic).
- `adapters/secondary/` — infrastructure implementations (Postgres, etc.).
- `ports/` — interface definitions.

Affected domains: Auth, Chat, IAM, Workspaces, Organizations.

## Consequences

### Positive
- Business logic is technology-agnostic and testable without a running FastAPI app.
- Route prefixes remain stable; the refactor is non-breaking to API consumers.
- `ServiceRegistry` provides a single place to swap adapter implementations (e.g. for testing).

### Tradeoffs
- Significantly more files per domain; the directory tree is deeper and more verbose.
- Developers must follow the ports-and-adapters convention strictly; shortcuts break the abstraction.
- The `ServiceRegistry` is a global singleton at startup; it is not suitable for per-request service customization without additional extension points.
