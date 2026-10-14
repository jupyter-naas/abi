# Modules sign as themselves, register as themselves, and stay off the engine's subjects

## Status
Accepted.

## Date
2026-10-14

## Context
The 2026-10-13 review of the NATS branch (abi#1299) found three gaps in how an
SDK module is trusted:

- **Signing (A13).** Generated modules received the project's
  `NATS_JWT_SECRET`, which signs every service token. A module could sign a
  token for any identity, `api` and `engine` included.
- **Registration (A7).** Discovery bound a registration to the identity that
  made it, but not the module id to that identity. Another module could
  register under an existing module id and take part of its agent calls, its
  jobs and its app routes (`/app-html/remote/<module_id>/<app>/`).
- **Users (A8).** Nexus sends the signed-in user's id with each app request
  (`HttpRequest.user_id`). The app host checked that the caller held a valid
  token, then trusted whatever user id it named, so any token holder could act
  as any user.

On the broker, both users had every right
(`20261008_nats-broker-passwords.md`): the `module` user could listen on the
kernel services' and discovery's subjects, overhearing calls and the tokens in
their headers or answering in their place, and read and write the engine's
key-value buckets directly.

## Decision

### Module keys
A module signs its tokens with a key of its own, derived from the project
secret for one identity: `HMAC-SHA256(secret, "abi.module-key.v1:" + identity)`
(`naas_abi_core.engine.nats_auth.module_key`). Its tokens carry the JWT header
`kid: "module"`. The verifier derives the key from the token's `sub` and checks
the signature with it, so a key signs for its own identity only. No key exists
for a first-party identity (`api`, `engine`, `dagster`), and a module token
asserting one is refused.

Tokens without that header are still checked against the secret: the engine's
own processes keep it and may assert any identity. Modules never receive it.

- `naas_abi_sdk.service_token.ModuleToken(identity, key)` signs and refreshes a
  module's tokens; `token_from_env` reads `ABI_MODULE_KEY` (or an issued
  `ABI_SERVICE_TOKEN`). The module template and `naas-abi-module` use it, for
  the module's own module id.
- `abi module key <module_id>` prints a key. `abi new module` writes the
  module's key to `.env` (`ABI_MODULE_KEY_<NAME>`) for its Compose service, and
  `abi dev up` gives each `dev.modules` entry the key of its `identity`.
- The key needs no storage of its own and follows the secret: a new secret
  invalidates every module key.

### A module registers as itself
Discovery's NATS adapter accepts a registration only when the token's identity
is the descriptor's module id. A module's agents, jobs, models and apps can no
longer be claimed by another identity.

### Only Nexus speaks for a user
The SDK's app host passes a `user_id` to the app only from the `api` identity
(`app_host.USER_CALLERS`). Any other caller may call an app, but a request from
it that names a user is refused with `PERMISSION_DENIED` before the app runs.
The ASGI scope also carries the caller's identity:
`scope["abi"] = {"user_id": ..., "caller": ...}`.

### The module broker user stays off the engine
`naas_abi_core.engine.nats_permissions.MODULE_PERMISSIONS`, in every broker a
project runs (the Docker `nats.conf`, the one `abi dev` writes): the `module`
user may not subscribe to `abi.svc.>`, `abi.discovery.>` or `$KV.>`, nor
publish to `$KV.>` or the JetStream API's stream delete, message delete,
snapshot, restore, peer, leader, meta, server and account subjects. It still
calls every service and discovery, serves its own subjects, creates and updates
its job and bus streams, purges its schedules, and stores claim checks in the
object store. The `abi` user keeps every right.

## Alternatives considered
**Issued long-lived tokens.** The operator issues a token per module (no key).
Simpler for the module, but a token lasts as long as it is valid, with no
refresh short of a new deployment, and a long expiry is a bearer credential.
A key lets the module refresh hourly tokens itself.

**Per-module NATS users, NKeys or auth callout.** The broker would give each
module the subjects it declares, which also stops one module from listening on
another's subjects. That needs a user per module in `nats.conf`, or `nsc` and a
resolver, or a callout service checking ABI's own tokens. It is the next step
(see `20261008_nats-broker-passwords.md`, "Auth callout").

**Bind module ids in the discovery service rather than in its NATS adapter.**
The service's unit tests treat the owner as an opaque lease holder; the adapter
is where the token is verified, so the identity rule sits next to it.

## Consequences
- A module can no longer sign as `api`, `engine` or another module, register
  under another module id, or act for a user. What a module's token proves now
  matches what the services and Nexus assumed.
- Breaking for existing SDK modules: a module that signed its own tokens from
  `NATS_JWT_SECRET` must sign with its module key, as its module id, and an
  identity that is not its module id is refused at registration. `dev.modules`
  entries declare `identity:` when their name is not the module id.
- A broker that runs modules must apply `MODULE_PERMISSIONS` to the `module`
  user. A module that subscribed to the engine's subjects or used `$KV`
  directly stops working there.
- Still open: all modules share the `module` user, so a module can listen on
  another module's subjects (`abi.mod.<project>.>`, `abi.agent.<project>.>`)
  and read the tokens Nexus and other callers send there, for their lifetime
  (one hour). It can also read the engine's key-value buckets through the
  JetStream API (`$JS.API.DIRECT.GET`), and purge or update any stream. Modules
  must still be trusted code until per-module broker users exist.
- Rotating `NATS_JWT_SECRET` rotates every module key; there is no way to
  revoke one module's key alone.
