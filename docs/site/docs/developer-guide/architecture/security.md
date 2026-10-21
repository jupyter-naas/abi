---
sidebar_position: 2.4
title: "Security Model"
---

# Security Model

A NATS deployment has four layers of protection: the **broker** admits only
known clients and, through its auth callout, confines each module to the
subjects its approved policy allows, **engine tokens** say who makes each call,
**IAM policies** decide what that caller may do (deny by default), and **grants**
let Nexus users open remote apps. This page describes each one and, as plainly,
what they do not cover yet. The design is in
[`docs/adr/20261013_engine-tokens-service-accounts-broker.md`](https://github.com/jupyter-naas/abi/blob/main/docs/adr/20261013_engine-tokens-service-accounts-broker.md).

## Broker users and the auth callout

The broker that `abi deploy local` and `abi dev up` run declares two static
users and an auth callout:

| User | Password (`.env`) | For |
|---|---|---|
| `engine` | `NATS_ENGINE_PASSWORD` | The engine's processes: kernel services, API, Nexus, jobs. Every subject but `$SYS`. |
| `auth` | `NATS_AUTH_PASSWORD` | The engine's auth callout responder, nothing else. |

Every other connection is asked of the engine: a module, script or CI job logs
in as `sa` with its **service key** (`abi_sk_...`) as the password, and gets
the subjects its approved policy allows (below), signed by the engine with the
account seed `NATS_AUTH_CALLOUT_SEED`. The broker trusts that seed's public key
(`NATS_AUTH_CALLOUT_ISSUER`).

- A client without a valid user and password or key is refused: a coding
  workspace, a CI job, or another machine on the network.
- The engine passes its credentials in the URL:
  `nats://engine:{{ secret.NATS_ENGINE_PASSWORD }}@nats:4222`. A module's
  `ABI_NATS_URL` carries no login: `nats://nats:4222`.
- `abi deploy local` generates the passwords and the seed (it replaces an empty
  or short password); `abi dev up` and `abi stack start` write them when they
  are missing. The Compose `nats` service refuses to start without them.
- The Compose stack publishes the client and monitoring ports on 127.0.0.1
  only; containers reach the broker as `nats:4222`.
- Users issued by the callout expire within five minutes (ten at most); the SDK
  reconnects every two minutes, so a revoked key, a suspended account or a
  narrowed manifest reaches the broker within that time. Services enforce every
  change at once.

`.deploy/docker/nats/nats.conf` (written by `abi deploy local --regenerate`, and
the broker config `abi dev up` writes) holds the users and the callout.
Regenerate after each CLI upgrade. Because modules may not create streams, the
engine that hosts discovery creates the jobs stream and the claim-check store
at start.

## Engine tokens

Every request over NATS carries a short-lived JWT in its headers. The engine
signs it with ES256 keys it generates and rotates every 30 days, kept in the
secret service; the public keys are a JWKS at `abi.iam.v1.jwks` and, over HTTP,
`/.well-known/abi-jwks.json` on the API. No token lives longer than ten
minutes, and there is no shared signing secret: modules never hold a signing
key. The subject (`sub`) is the caller's principal, the receiving service
verifies the token before it runs anything, and IAM then decides whether that
principal may do what it asks.

### Module identities

Every remote module runs as a **service account**
`module/<project>/<module_id>` with its own key:

```bash
abi iam service-account create module/<project>/<module_id> --key   # the key is printed once
abi iam module list --status pending
abi iam module approve module/<project>/<module_id>
```

- The module logs in to the broker with the key (`ABI_SERVICE_KEY`) and
  exchanges it for tokens of ten minutes at most, renewed at half their life.
  Keys are stored hashed, shown once, revocable (`abi iam key revoke`),
  rotatable and optionally expiring.
- At start the module submits a **permission manifest** (a policy document,
  by default derived from its declared dependencies) and waits. Until an admin
  approves, narrows or rejects it, the module holds only a bootstrap policy
  (register, renew and unregister its own record, submit and read its own
  manifest). `abi dev up` approves its dev modules itself.
- The broker confines the module to the subjects of that policy: the request
  subjects of the services it may use, its own hosting subjects, its own
  inbox prefix and the JetStream consumers it needs. It cannot listen on the
  engine's service, discovery or RPC overflow subjects, `$JS.>` or `$KV.>`,
  nor administer streams.
- Discovery registers a module only under its own account, so no module can
  claim another's agents, jobs or app routes. No module can sign as `api` or
  `engine`.
- `abi new module` and `abi dev up` set this up: `abi dev up` creates the
  account and a fresh key per run; for Compose, the key goes in `.env` as
  `<NAME>_SERVICE_KEY`.
- A leaked module key exposes only that module's approved permissions;
  revoking it ends access within ten minutes, suspending the account at once.

### Tokens sent to a module are bound to it

A token sent to a module instance (its agents, models and apps) carries the
instance id as its audience and lasts five minutes. That module cannot replay
it against the engine's services or another module. Only a key (or the
engine) can mint a token bound to the module called.

### Platform operations

Listing every module's document namespaces and evicting a discovery instance
accept only the `api` and `engine` identities. In the Nexus System app, every
change to a service's data (create, replace, delete, reveal a secret) is
audited before it runs, needs the resource id typed back, and is open to super
admins only.

## Remote app grants

A remote app's page is sandboxed and holds a **grant** in its URL instead of a
session: one app, one user, one workspace, 8 hours at most. A grant carries
no `sub`, so it is never a session token. It ends at the user's logout on any
device or `POST /api/apps/remote-grant/revoke`. Logs, activity events and traces show
`/app-remote/[grant]/...`, never the grant itself. See
[Remote apps](./remote-apps#sandbox-and-grants).

App link tokens (`POST /api/apps/access-token`, scope `app-html`) open
`/app-html/` only; they no longer authenticate `/api/*` or the WebSocket.

## Known limits

These are not covered in 3.0. Plan deployments around them.

- **One NATS account per project.** Projects are separated by subject prefix,
  not by NATS accounts: every connection is in the same account.
- **The `engine` user reaches every subject but `$SYS`.** Keep its password to
  the engine's processes.
- **Broker permissions lag behind policy** by up to the callout user's life
  (five minutes by default, ten at most): an approval, a narrowed policy or a
  revoked key reaches the broker at the next connection. Services apply it at
  once.
- **A `nats_rpc` adapter logs in with a broker password** (`engine`); it does
  not yet log in through the callout with its key.
- **A module can still drop a pub ack or an empty message on another topic.**
  The server answers a module's JetStream requests on the reply subject the
  module chose, and streams capture what lands there. Job hosts take only the
  triggers the engine sealed. Separate NATS accounts would close this
  (proposed).
- **Modules must run the SDK of the same release as the engine.** An older SDK
  creates its own streams, consumers and job messages, which the broker now
  refuses.
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
