# ADR: Config-Driven Tenant Branding and Startup Provisioning

- Status: Accepted
- Date: 2026-02-19

## Context

Nexus deployments needed to support multi-tenant white-labeling: different tab titles, favicons, logos, accent colors, and auth-page styles per deployment. Initial implementations hardcoded branding in frontend assets or required manual database seeds, making it expensive to configure a new deployment and impossible to express deployment-specific branding as code.

Separately, bootstrapping initial users, organizations, workspaces, and memberships required manual API calls or migration scripts that were not reproducible from config.

## Decision

Introduce a config-driven tenant branding and startup provisioning system:

1. **Branding**: Tab title, favicon, logo URLs, primary/accent colors, and auth-page styling are declared in the module `config.yaml`. These are served by a new public `/api/tenant` endpoint and consumed by a `TenantProvider` React context in the frontend. No recompilation or asset rebuild is required to rebrand a deployment.

2. **Startup provisioning**: Users, organizations, workspaces, and memberships declared in module config are upserted at API startup using key-based identity resolution. Generated bootstrap passwords are synced to the secret service when enabled. This makes initial deployment state fully reproducible from config.

## Consequences

### Positive
- Deployments are fully configurable from `config.yaml` without touching code or database directly.
- Startup provisioning is idempotent; re-running it on a live system does not duplicate data.
- Branding changes deploy with a config update and service restart, not a frontend build.

### Tradeoffs
- Bootstrapped passwords are auto-generated; operators must retrieve them from the secret service on first deploy.
- Startup provisioning runs on every API boot — its duration scales with the number of provisioned entities.
- Branding config is served unauthenticated via `/api/tenant`; sensitive values must not be placed there.
