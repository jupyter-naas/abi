# ADR 0001: Single Source of Truth for CORS

- Status: Accepted
- Date: 2026-03-04

## Context

The ABI API and the embedded Nexus API were both configuring CORS independently:

- `api.cors_origins` in top-level engine configuration
- `modules[].config.nexus_config.cors_origins_str` / `cors_origins` in Nexus module configuration

Because both layers attach middleware on the same FastAPI app, duplicated CORS configuration creates drift risk and inconsistent runtime behavior.

## Decision

Use top-level `api.cors_origins` as the single source of truth for CORS in ABI deployments.

To enforce this:

- Remove CORS fields from `naas_abi.NexusConfig`.
- Stop generating Nexus CORS entries in project config templates.
- Propagate `engine.configuration.api.cors_origins` to Nexus at runtime through shared app state.
- Use that shared origin list for both Nexus HTTP middleware and Nexus Socket.IO configuration.

In standalone Nexus mode (without ABI engine integration), Nexus falls back to `settings.frontend_url` as its CORS origin.

## Consequences

### Positive

- Eliminates duplicated CORS configuration and environment drift.
- Makes operator responsibility explicit: set `api.cors_origins` correctly in `config.yaml`.
- Keeps ABI API and Nexus API CORS behavior aligned.

### Tradeoffs

- Legacy Nexus CORS fields in module config are now invalid and fail validation.
- Teams relying on Nexus-specific CORS overrides must migrate to top-level `api.cors_origins`.
