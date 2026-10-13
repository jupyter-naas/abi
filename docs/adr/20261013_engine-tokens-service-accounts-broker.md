# Engine-signed tokens, service accounts and broker permissions

Status: Accepted

Date: 2026-10-13

Discussion: [#1314](https://github.com/jupyter-naas/abi/issues/1314).
Specification: [`docs/specs/rfcs/20261013_identity-and-authorization.md`](../specs/rfcs/20261013_identity-and-authorization.md), §8 to §10.
Supersedes the Stage 1 token decision in `docs/specs/rfcs/20260910_distributed-modules-nats-jetstream.md`
("Stage 1's JWT is deliberately minimal") and extends `20261008_nats-broker-passwords.md`.

## Context

**Every NATS call carries an HS256 JWT signed with one shared `NATS_JWT_SECRET`** (`engine/nats_auth.py`):
claims `{sub, iat, exp}`, valid 1 hour.

- `abi dev` and the module template hand that secret to every remote module, so any module can sign tokens as
  `api` or `engine`.
- The broker has two users, `abi` and `module`, and both may publish and subscribe to anything.
- Discovery does not bind a module's logical name to its credential.

**Nexus mints its own narrow tokens with keys derived from `secret_key`:**

- app-html links;
- remote-app grants;
- preview links;
- a 30-day coding-agent JWT, which works as a full session (bug a).

It calls remote agents as the shared identity `api`, and passes the end user as unauthenticated text.

## Decision

- **The engine signs its tokens with ES256.**
  - Keys have a `kid` and rotate every 30 days.
  - Private keys live in the secret service, sealed to the engine.
  - Public keys are published as a JWKS over NATS (`abi.iam.v1.jwks`), and over HTTP by Nexus.
  - Modules never hold a signing key.
  - HS256 and `NATS_JWT_SECRET` are removed, with no dual mode: this is a major release.
- **Claims.**
  - `iss`, `sub` (principal id), `aud`, `kind`, `jti`, `iat`, `nbf` and `exp`.
  - `act` (RFC 8693) when an actor works for a user.
  - `grp` for mapped IdP groups.
  - `abi_scope` for narrowing.
  - No access token lives longer than 10 minutes. Verifiers refuse longer ones.
- **One audience per token.**
  - `abi:session` for Nexus sessions.
  - `abi:nats` for service accounts.
  - A delegated audience for each narrow kind: `agent`, `app`, `preview`, `coding`, `api-key`.

  Delegated tokens come from token exchange (RFC 8693), only narrow, and are never accepted as a session.
- **Every remote module, script and CI job runs as a service account.**
  - Keys (`abi_sk_…`) are random, stored hashed, shown once, revocable, rotatable and optionally expiring.
  - They are exchanged for engine tokens (`ABI_SERVICE_KEY` replaces `ABI_SERVICE_TOKEN` and
    `NATS_JWT_SECRET`).
  - Personal API keys (`abi_pk_…`) use the same mechanism with the `abi:delegated:api-key` audience.
- **A module declares a permission manifest,** a policy document. Defaults come from `ModuleDependencies`.
  - An admin approves it, narrows it or rejects it. Until then the module holds only a bootstrap policy
    (register, renew, unregister its own module record).
  - `abi dev up` approves automatically.
  - Discovery refuses a registration whose module name differs from the caller's service account.
- **The broker confines each module through NATS auth callout in the engine.**
  - The callout validates the module's key and assigns subject permissions derived from its approved policy:
    - request subjects for the services it has any allowed action on;
    - its own hosting subjects, which gain a service-account token;
    - its own inbox prefix;
    - the JetStream consumers it needs.
  - Everything else is denied.
  - The engine connects as a static user exempt from the callout. Its permissions are limited to what the
    kernel serves.
  - Resource-level decisions stay in the domain services.
- **`CallContext` is filled only from verified credentials.** It is set by one shared helper in the NATS
  dispatch path, by Nexus middleware (principal `api`, on behalf of the signed-in user) and by in-process
  inheritance.
  - `CallContext.principal_id` and `tenant_id` in the proto become reserved, and `HttpRequest.user_id` is
    informational.
  - `CallContext.workspace_id` remains as a request input: the target workspace of a create.

## Consequences

- **No module can impersonate `api`, `engine` or another module.** A leaked module key exposes only that
  module's approved permissions, and revoking it ends access within 10 minutes. Suspending its principal ends
  it at once.
- **Deployment changes.**
  - Each deployment creates one service account and key per module.
  - `abi dev up` does it automatically.
  - Deployed systems approve manifests with `abi iam module approve` or in the IAM UI.
- **Broker configuration changes.** `nats.conf` gains `auth_callout`, and the `module` user disappears from
  `abi dev`, the deploy template and `.deploy/docker/nats/nats.conf`.
- **Hosting subjects change.** Agent, app and model hosting subjects gain the service-account token. Callers
  read subjects from discovery records, so only hosts change.
- **Broker permissions lag behind policy.** They are recomputed when a connection is (re)established, and
  callout-issued users expire within an hour. Services enforce every change immediately, so the broker only
  narrows further.
- **Nexus's narrow tokens move to the engine issuer.** The 30-day coding-agent JWT (bug a) becomes a
  revocable environment key exchanged for 10-minute `abi:delegated:coding` tokens.
