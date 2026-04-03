# ADR: `abi stack` CLI for Docker Service Management

- Status: Accepted
- Date: 2026-02-16

## Context

Developers working on ABI locally needed to orchestrate multiple Docker services (Postgres, Fuseki, RabbitMQ, MinIO, Nexus web, Nexus API, etc.). This required memorizing and composing raw `docker compose` commands, with no unified way to check service readiness, tail logs by logical name, or get a health overview. Onboarding friction was high.

## Decision

Introduce an `abi stack` command group in the `naas-abi-cli` package with the following subcommands:
- `abi stack start` - starts all Docker Compose services.
- `abi stack stop` - stops all services.
- `abi stack status` - probes service availability and prints a health summary.
- `abi stack logs [service]` - streams logs for a named logical service (e.g. `core`, `api`, `web`).
- `abi stack tui` - opens a Textual-powered terminal UI for interactive service inspection.

Service readiness probing (TCP/HTTP checks) is encapsulated in a `StackRuntime` module, separate from the CLI layer, making it testable independently.

## Consequences

### Positive
- Single entry point for all local stack operations; no raw Docker knowledge required.
- Readiness probes give deterministic startup feedback instead of timing-based waits.
- Logical service names (e.g. `core`) abstract over the underlying Docker Compose service names.

### Tradeoffs
- The CLI is tightly coupled to the `docker-compose.yaml` layout; structural changes to Compose require CLI updates.
- The Textual TUI adds a non-trivial dependency and may not work well in all terminal environments.
- Stack commands are local-dev focused; they are not intended for production orchestration.
