# ADR: Python Monorepo Split into naas-abi-core / naas-abi / naas-abi-marketplace / naas-abi-cli

- Status: Accepted
- Date: 2025-11-30

## Context

The ABI codebase was a single Python package under `src/`. As the project grew, several problems emerged:

- Core infrastructure (triple store, vector store, services, ports) was entangled with application-level code (agents, pipelines, workflows).
- Marketplace modules (third-party integrations) were bundled with the core runtime, forcing users to install all dependencies even if they only needed a subset.
- The CLI was tightly coupled to the application layer, making it hard to release independently.
- There was no clean way to publish core infrastructure as a reusable library for teams building on top of ABI without also pulling in marketplace integrations.

## Decision

Split the monorepo into four focused packages managed with `uv` workspaces:

| Package | Path | Responsibility |
|---------|------|----------------|
| `naas-abi-core` | `libs/naas-abi-core/` | Core infrastructure: ports, service interfaces, base adapters, engine bootstrap |
| `naas-abi` | `libs/naas-abi/` | Application layer: built-in agents, pipelines, Nexus app, standard modules |
| `naas-abi-marketplace` | `libs/naas-abi-marketplace/` | Optional third-party integrations: LinkedIn, Salesforce, Google, etc. |
| `naas-abi-cli` | `libs/naas-abi-cli/` | CLI tooling: `abi` command, project scaffolding, stack management |

Dependencies flow in one direction: `naas-abi` depends on `naas-abi-core`; `naas-abi-marketplace` depends on `naas-abi`; `naas-abi-cli` depends on all three. The root `pyproject.toml` links all packages as editable sources for local development.

## Consequences

### Positive
- Teams can depend on `naas-abi-core` only, without pulling in marketplace integrations.
- Each package has its own versioning, changelog, and release cadence via semantic-release.
- `naas-abi-marketplace` can have heavy optional dependencies (Salesforce SDK, LinkedIn scrapers) isolated from the core runtime.
- CI checks can be scoped per package (`make check-core`, `make check-marketplace`).

### Tradeoffs
- Cross-package refactors require coordinated changes across multiple `pyproject.toml` files and package boundaries.
- Local development requires `uv sync --all-extras` at the root to wire all packages; partial installs can produce confusing import errors.
- The four-package structure adds release overhead: a single feature may require bumping versions in multiple packages.
