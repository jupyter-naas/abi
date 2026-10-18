---
sidebar_position: 2.4
title: "Security Model"
---

# Security Model

A NATS deployment has three layers of protection: the **broker** admits only
clients with a password and keeps modules off the engine's subjects, **service
tokens** say which process makes each call, and **grants** let Nexus users open
remote apps. This page describes each one and, as plainly, what they do not
cover yet.

## Broker passwords

The broker that `abi deploy local` and `abi dev up` run declares two users:

| User | Password (`.env`) | For |
|---|---|---|
| `abi` | `NATS_ABI_PASSWORD` | The engine's processes: kernel services, API, Nexus, jobs. Every right. |
| `module` | `NATS_MODULE_PASSWORD` | Remote modules (SDK). Restricted (below). |

- A client without a valid user and password is refused: a coding workspace, a
  CI job, or another machine on the network.
- Clients pass their credentials in the URL:
  `nats://abi:{{ secret.NATS_ABI_PASSWORD }}@nats:4222` for the engine,
  `ABI_NATS_URL=nats://module:<NATS_MODULE_PASSWORD>@nats:4222` for a module.
- `abi deploy local` generates both passwords (it replaces an empty or short
  one); `abi dev up` writes them when they are missing. The Compose `nats`
  service refuses to start without them.
- The Compose stack publishes the client and monitoring ports on 127.0.0.1
  only; containers reach the broker as `nats:4222`.

The `module` user may not:

- subscribe to the engine's subjects (`abi.svc.>`, `abi.discovery.>`,
  `abi.rpc.>`), where calls carry their callers' tokens, nor to `_INBOX.>`
  (the engine's and Nexus's replies), `$JS.>` or `$KV.>`. Modules use their own
  inbox prefix, `_INBOX_MODULES`;
- write `$KV.>`, create, update or delete streams, delete consumers, or use the
  JetStream direct get, server, meta and account API.

The rules live in `naas_abi_core.engine.nats_permissions` and are written into
`.deploy/docker/nats/nats.conf` by `abi deploy local --regenerate` (and into the
broker config `abi dev up` writes). Regenerate after each CLI upgrade. Because
modules may not create streams, the engine that hosts discovery creates the
jobs stream and the claim-check store at start.

## Service tokens

Every request over NATS carries a short-lived JWT in its headers, signed with
the project's `NATS_JWT_SECRET` (32 bytes or more). Its subject (`sub`) is the
caller's identity: `api` (Nexus), `engine`, or a module id. The receiving
service verifies it before it runs anything. A token proves **which of your
processes is calling**; it does not, by itself, limit what that process may do.

### Module identities

Remote modules never receive `NATS_JWT_SECRET`. Each gets a **module key**
derived from it for one module id:

```bash
abi module key <module_id>   # prints the key; the module gets it as ABI_MODULE_KEY
```

- A module key signs tokens for its own module id only. No key exists for the
  first-party identities (`api`, `engine`, `dagster`).
- Discovery registers a module only under a token for its own module id, so no
  module can claim another's agents, jobs or app routes.
- `abi new module` writes the module's key to `.env`
  (`ABI_MODULE_KEY_<NAME>`) for its Compose service; `abi dev up` gives each
  `dev.modules` entry the key of its module id.
- In code, `ModuleToken(module_id, key)` (`naas_abi_sdk.service_token`) signs
  and refreshes the tokens; `token_from_env(os.environ, module_id)` reads
  `ABI_MODULE_KEY`, else an issued `ABI_SERVICE_TOKEN`.
- A new `NATS_JWT_SECRET` changes every module key. There is no way to revoke
  one module's key alone.

### Tokens sent to a module are bound to it

A token sent to a module instance (its agents, models and apps) carries the
instance id as its audience and lasts five minutes. That module cannot replay
it against the engine's services or another module. A static
`ABI_SERVICE_TOKEN` cannot be bound, so a module holding only one cannot call
other modules.

### Platform operations

Listing every module's document namespaces and evicting a discovery instance
accept only the `api` and `engine` identities. In the Nexus System app, every
change to a service's data (create, replace, delete, reveal a secret) is
audited before it runs, needs the resource id typed back, and is open to super
admins only.

## Remote app grants

A remote app's page is sandboxed and holds a **grant** in its URL instead of a
session: one app, one user, one workspace, 8 hours at most. A grant is signed
with a key derived from the API secret and carries no `sub`, so it is never a
session token. It ends at the user's logout on any device, a password change,
or `POST /api/apps/remote-grant/revoke`. Logs, activity events and traces show
`/app-remote/[grant]/...`, never the grant itself. See
[Remote apps](./remote-apps#sandbox-and-grants).

App link tokens (`POST /api/apps/access-token`, scope `app-html`) open
`/app-html/` only; they no longer authenticate `/api/*` or the WebSocket.

## Known limits

These are not covered in 3.0. Plan deployments around them.

- **Modules must be trusted code.** All remote modules share the `module`
  broker user, so a module can:
  - subscribe to another module's subjects (`abi.mod.>`, `abi.agent.>`) and
    inbox (`_INBOX_MODULES.>`), see its requests and replies, replay a token
    sent to that module (to that module only, within its five minutes), and
    race forged answers to that module's callers;
  - read any stream through the JetStream consumer and message-get API: the
    jobs stream (every module's triggers and payloads), the claim-check store,
    bus and event streams, and the engine's key-value buckets, discovery's
    registry and the key-value service's data included;
  - purge any stream, and ack, nak or terminate any message it can fetch;
  - take over another module's jobs: fetch from its job consumer, recreate it
    with another configuration, and publish triggers or cancels for its jobs,
    which carry no token.

  Per-module broker users (or NATS auth callout) are the next step.
- **One project per broker account.** Projects are separated by subject prefix
  and their signing secret, not by NATS accounts.
- **No TLS.** Traffic to the broker is not encrypted. Keep the broker on a
  private network; a module on another machine reaches it through a VPN or an
  SSH tunnel.
- **The monitoring endpoint has no authentication.** Keep port 8222 on the
  private network (the generated stack binds it to 127.0.0.1).
- **No per-user authorization between modules.** A module receives the user id
  Nexus asserts for app requests; agent invocations carry the caller's
  identity, not the end user's rights. Document namespaces are not security
  boundaries.

→ [Observability](./observability)
