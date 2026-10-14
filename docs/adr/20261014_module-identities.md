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

Tokens are bearer tokens. Nexus and the engine send theirs (`api`, `engine`)
with every call to a module's agents, models and apps, so a module did not
need to sign anything to act as them: it could keep the token it was sent and
replay it, for its hour, against the engine's services or another module.

On the broker, both users had every right
(`20261008_nats-broker-passwords.md`). The `module` user could listen on the
kernel services' and discovery's subjects, overhearing calls and the tokens in
their headers or answering in their place, and on `_INBOX.>`, where every
reply to the engine and Nexus goes (secret values included). Through the
JetStream API it could create a stream on `abi.svc.>` and read the engine's
calls from it, and read or write the engine's key-value buckets.

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
  module's tokens; `token_from_env` reads `ABI_MODULE_KEY` (preferred) or an
  issued `ABI_SERVICE_TOKEN`. The module template and `naas-abi-module` use it,
  for the module's own module id.
- `abi module key <module_id>` prints a key. `abi new module` writes the
  module's key to `.env` (`ABI_MODULE_KEY_<NAME>`) for its Compose service,
  from the `NATS_JWT_SECRET` already there (it makes none up). `abi dev up`
  gives each `dev.modules` entry the key of its module id: its `identity:`,
  else the `module_id` of the `ABIModule` its package exports; it refuses a
  module whose id it cannot tell.
- The key needs no storage of its own and follows the secret: a new secret
  invalidates every module key.

### Tokens sent to a module are bound to it
A token sent to a module instance (`abi.agent.<project>.<instance>...`,
`abi.mod.<project>.<instance>...`) carries `aud: <instance id>` and lasts five
minutes (`nats_auth.BOUND_TTL`). The SDK's `Transport` asks its token source
for one (`for_audience`) for every call to such a subject; `ModuleToken` and
the engine's `nats_auth.ServiceTokenSource` provide it (one cache,
`naas_abi_sdk.service_token.TokenCache`), and a static token cannot call a
module. A bound token is handed out again only in its first 30 seconds, so it
reaches the module with at least 4.5 minutes left: a module authorizes a call
once it takes it from its queue, and callers stop waiting long before that
(65 s for an app request, 120 s for a model). Discovery's `authorize_agent`,
`authorize_model` and `authorize_app` accept a caller's token only when it is
bound to the instance asking. Every other verifier (the engine's services,
discovery's own calls) refuses a token with an audience. So a token a module
was sent works only against that module, for five minutes.

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
project runs (the Docker `nats.conf`, the one `abi dev` writes). The `module`
user may not:

- subscribe to the subjects the engine serves, where calls carry their callers'
  unbound tokens: `abi.svc.>`, `abi.discovery.>` and `abi.rpc.>` (RPC
  overflow: an upload above the broker limit, Nexus's included); nor to
  `_INBOX.>` or `$KV.>`. Module connections use their own inbox prefix,
  `_INBOX_MODULES` (`run_module` sets it, and `Transport` for a URL logged in
  as `module`), so the engine's and Nexus's replies, on `_INBOX.>`, never reach
  a module;
- publish to `$KV.>`, or to the JetStream API's stream create, update,
  delete, message delete, snapshot, restore, peer and leader subjects,
  consumer delete, direct get, or server, meta and account API.

Modules may not create streams, so the engine creates the ones they use: the
engine hosting discovery creates the project's jobs stream and the claim-check
object store at start, before discovery serves
(`nats_permissions.prepare_module_streams`). SDK modules host jobs only with
discovery, so that engine is the one their jobs stream belongs to. A module
that finds a stream missing, or a bus queue's stream that does not exist,
raises `StreamNotCreated`, which says so. The `abi` user keeps every right.

## Alternatives considered
**Issued long-lived tokens.** The operator issues a token per module (no key).
Simpler for the module, but a token lasts as long as it is valid, with no
refresh short of a new deployment, and a long expiry is a bearer credential.
A key lets the module refresh hourly tokens itself and bind each call.

**Per-module NATS users, NKeys, NATS accounts or auth callout.** The broker
would give each module the subjects and streams it declares, which also stops
one module from listening on another's subjects or reading streams. That needs
a user per module in `nats.conf`, or `nsc` and a resolver, or a callout
service checking ABI's own tokens. It is the next step (see
`20261008_nats-broker-passwords.md`, "Auth callout").

**Allow-listing the JetStream API by stream name.** NATS permissions match
whole subject tokens, so a stream name can be allowed exactly but not by
prefix. Bus queue streams are named per topic (`naas-abi-<hash>`), and job
streams per project, so an allow-list would have to be generated per project
and would still break bus queues on new topics. Denying stream creation
closes the capture of other subjects; reading existing streams stays open
(below).

**Bind module ids in the discovery service rather than in its NATS adapter.**
The service's unit tests treat the owner as an opaque lease holder; the adapter
is where the token is verified, so the identity rule sits next to it.

## Consequences
- A module can no longer sign as `api`, `engine` or another module, register
  under another module id, or name a user to another module's app with its own
  token. A token it is sent is refused by the engine's services and by any
  other module, and it cannot listen where the engine's callers send their
  unbound tokens. What one module can still do to another is listed below.
- Breaking for existing SDK modules: a module that signed its own tokens from
  `NATS_JWT_SECRET` must sign with its module key, as its module id; an
  identity that is not its module id is refused at registration. A module
  holding only a static `ABI_SERVICE_TOKEN` cannot call another module. A
  broker that runs modules must apply `MODULE_PERMISSIONS` to the `module`
  user; a module that subscribed to the engine's subjects or replies, used
  `$KV` directly, or created streams stops working there. A module's bus queue
  works only on a topic whose stream the engine created.
- Still open, until modules get broker users of their own. All modules share
  the `module` user, so a module can:
  - subscribe to another module's subjects (`abi.mod.>`, `abi.agent.>`) and
    inbox (`_INBOX_MODULES.>`): it sees the requests and replies sent there,
    and can replay a token sent to that module, to that module only, within
    its five minutes (a token Nexus sent to that module's app lets it name a
    user there);
  - read any stream through the JetStream consumer API and
    `$JS.API.STREAM.MSG.GET`: the jobs stream (every module's triggers and
    payloads), the claim-check store, bus and event streams, and the engine's
    key-value buckets (`KV_*`, discovery's registry and the key-value
    service's data included);
  - purge any stream (`$JS.API.STREAM.PURGE`), and ack, nak or terminate any
    message it can fetch (`$JS.ACK.>`);
  - take over another module's jobs: fetch from its durable job consumer
    (taking its triggers), create that consumer again with another
    configuration (changing what it delivers), and publish triggers or
    cancels for its jobs straight to `abi.jobs.<project>.trigger|cancel.<hash>`,
    which carry no token.

  Modules must still be trusted code.
- A call that waits more than about 4.5 minutes in a module's queue before the
  module takes it is refused (`UNAUTHENTICATED`, its bound token expired). Only
  uploads hold a module's call slots that long (A11, remote app serving).
- Rotating `NATS_JWT_SECRET` rotates every module key; there is no way to
  revoke one module's key alone.
