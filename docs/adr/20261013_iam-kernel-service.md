# IAM is a kernel service with its own SQL store

Status: Accepted

Date: 2026-10-13

Discussion: [#1314](https://github.com/jupyter-naas/abi/issues/1314).
Specification: [`docs/specs/rfcs/20261013_identity-and-authorization.md`](../specs/rfcs/20261013_identity-and-authorization.md), §11.

## Context

**Authorization has to run inside the engine's domain services,** for Nexus REST, SDK modules over NATS and
in-process callers alike. The policy data must therefore be reachable from every engine process, and from
modules over NATS. Modules need it to register catalogs, exchange keys and fetch the JWKS.

**Nexus has a `services/iam`,** but it is a scope matcher inside the API process. Its role data is spread over:

- `organization_members`;
- `workspace_members`;
- `workspace_resource_policies`;
- `users.is_superadmin`.

**Kernel services already store data portably.** The Document Service is the usual home for mutable state.
But IAM differs from other state:

- **It authorizes the Document Service itself.** Storing policies there is circular: reading a policy would
  need a policy.
- **It needs relational guarantees:**
  - unique `(issuer, sub)` users;
  - unique service-account names and key ids;
  - attachments that reference policies and principals;
  - atomic approval of a manifest together with its policy.
- **It is on the hot path of every call.** It needs a store it controls directly, with predictable queries.

## Decision

- **`iam` is a kernel service in `naas-abi-core`** (`services/iam/`), with the usual layout:
  - port, domain service, primary and secondary adapters, factory, tests;
  - its own `AGENTS.md` and a row in the root Service Map.
- **It owns:**
  - principals (users, groups and service accounts, each with a status);
  - IdP group mappings;
  - policies, attachments and managed roles;
  - service-account and personal keys;
  - module manifests;
  - placements and the org/workspace scope registry;
  - action catalogs;
  - seals;
  - link grants;
  - signing-key metadata.
- **It keeps its own SQL store** behind an `IAMStore` port, not the Document Service.
  - Adapters: SQLite (the default, `storage/iam/iam.sqlite`, used by `abi dev`), PostgreSQL (Docker
    templates and production) and in-memory (tests).
  - They share one generic contract test.
  - Private signing keys stay in the secret service, sealed to the engine. The store keeps only their
    metadata.
- **It is reachable everywhere:**
  - in process as `engine.services.iam`;
  - over NATS under `abi.iam.v1.*` (proto `iam/v1`);
  - through the SDK as `engine.services.iam`;
  - through the auth-callout responder for the broker.
- **Authorization goes through an `IAuthorizer` port,** shaped like OpenFGA (`check`, `filter`, `explain`).
  - The `policy` adapter is the default.
  - `allow_all` is an explicit opt-out.
  - Domain services call `iam.require` and `iam.filter`, which read the caller from `CallContext`.
- **IAM authorizes its own operations** with its own `iam:*` catalog.
- **Freshness.**
  - Effective policies, placements and statuses are cached in every checking process.
  - IAM publishes `abi.iam.v1.changed` with a revision on every change, so caches drop affected entries at
    once and everything after 60 seconds.

## Consequences

- **Every kernel service gains a dependency on IAM** at boot. IAM loads first, then services register their
  catalogs before serving.
- **The engine stores one more database.**
  - Backups and the Docker templates include it.
  - PostgreSQL deployments add an `IAM_POSTGRES_DSN` secret.
- **Nexus's role tables migrate into IAM attachments** (subtask 11 of #44), leaving one source of truth.
  Nexus keeps profile data, keyed by the IAM principal id.
- **Suspensions and grants apply right away.** In process they take effect at once, and over NATS within the
  change event's delivery. Bounded caches limit the damage of a missed event.
- **An OpenFGA adapter can be added later** behind `IAuthorizer` without changing any caller.
