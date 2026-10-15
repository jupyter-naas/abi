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

## As built (2026-10-15, #60)

Implemented as decided, with these differences:

- **Signing keys.** `services/iam/tokens.py`: kid `<yyyymmdd>-<8 hex>`, rotation every 30 days
  (`rotation_days`). The next key is published 15 minutes before it signs and the previous one stays in the
  JWKS 20 minutes after. Private halves are in the secret service under `iam/signing-keys/<kid>`. The JWKS
  names the issuer, `urn:abi:engine:<install id>`. Nexus serves it at `/.well-known/abi-jwks.json`.
- **Who holds what.** The serving engine signs its own tokens and verifies against its own keys, with no NATS
  hop. A client-role engine exchanges the engine account's key, which the serving engine keeps in
  `iam/service-keys/engine` (one such key at a time), or `nats.service_key`. A `nats_rpc` adapter takes a
  `service_key` of the owning engine's IAM.
- **The manifest goes to IAM, not to discovery.** At start the SDK calls `abi.iam.v1.submit_manifest` and
  waits for approval, then registers. A module's bootstrap policy (`builtin.module_bootstrap`) allows
  registering, renewing and unregistering its own module record and submitting and reading its own manifest.
  Module accounts are named `module/<project>/<module_id>`. Approval writes the managed policy
  `module.<project>.<module_id>`, with `${module.id}` and `${module.project}` bound.
  `services.iam.modules.auto_approve: true` approves every manifest on submission; only the `abi dev up`
  overlay sets it.
- **Broker logins.** Two static users skip the callout. `engine` reaches every subject but `$SYS`, not only
  what the kernel serves: the API, Nexus and jobs run on it and use many subjects. Narrowing it is left for
  later. `auth` answers the callout. Everyone else logs in as `sa`, with a key as password. The responder
  signs the user with the account seed `NATS_AUTH_CALLOUT_SEED`, and the user expires within an hour
  (`nats.auth_callout.user_ttl_seconds`).
- **Subjects a module gets** (`services/iam/broker.py`). A permission ending in `*` also matches a client's
  literal `>` or `*` token, so every grant keeps the account's own tokens before its first wildcard:
  - IAM's request subjects, one by one (IAM authorizes each operation itself). Never `abi.iam.v1.changed`.
    An engine treats a change notice as a hint: it reads the store's revision and drops its caches when that
    differs from the last one it saw, whatever the notice says (a forged or huge revision stops nothing; a
    restored store counts too);
  - the engine's broker control `abi.broker.v1.<operation>` (below);
  - publishing to `_INBOX.>`, since replies, apps' request bodies and run updates go to inboxes, and to
    the RPC overflow host `abi.rpc.overflow.>`, whose sessions belong to the caller that opened them;
  - **no response permissions.** With them a module could answer any reply subject of a message it receives,
    and it picks the reply subject of what it sends itself (its inbox, its topic). It answers on `_INBOX.>`;
  - subscribing to its own inbox prefix `_INBOX.<key id>` (the SDK sets it) and to its hosting subjects
    `abi.agent.<project>.<sa>.>` and `abi.mod.<project>.<sa>.>`, where `<sa>` is the ULID part of its
    `sa_` id;
  - for each allowed action, the action's catalog subjects. A service without a registered catalog grants
    its whole prefix `abi.svc.<service>.v1.>`. Discovery actions add the hosting subjects of the modules they
    reach, in the module's project (for another account, the projects its resources name), and the event
    service adds `evt.>`;
  - **jobs**, only for job resources naming the module (`job/<project>/<module>/<job>`): the triggers and
    cancels the engine publishes for it on that module's jobs (`<module hash>` subjects). A module hosts the
    jobs its policy names: fetching from and acknowledging its consumers by exact name, its cancel subject.
    It writes nothing into the jobs stream: schedules make the server allow rollups there (whatever the
    stream's flag says), so one `Nats-Rollup: all` from a module would purge every module's triggers and
    schedules. The default manifest names each job;
  - **bus topics**, concrete, under no platform root (`abi`, `evt`, `_INBOX`, `$...`, `_...`) and nested in
    no other approved topic (refused when a manifest is submitted or approved): the topic, and fetching from and
    acknowledging the consumers of its queue stream;
  - **claim checks** under the scope they travel with: `abi.cc.t.<topic hash>.>` for a topic,
    `abi.cc.j.<project>.<module hash>.>` for a module's job triggers (writers: those who may trigger;
    readers: the host). The SDK stores them in the stream `ABI_CLAIM_CHECKS`; a module reads chunks back
    through the engine (`read_claim_check`, checked against what it may consume or host), never by direct get,
    and checks them against a SHA-256 in the reference.
- **The engine creates streams and consumers, and writes the jobs stream** (`engine/nats_broker_control.py`,
  `naas_abi_sdk/broker_control.py`). A stream's subjects and a consumer's filter and delivery subject travel in
  the request body, which the broker never reads, so a module creates none, and gets no stream info (a
  subjects filter would list every module's subjects). It asks the engine at `abi.broker.v1.<operation>` with
  its token: `ensure_topic`, `ensure_queue`, `ensure_job`, `set_schedules`, `trigger`, `cancel`,
  `ensure_claim_checks`, `read_claim_check`, `verify_trigger`. The engine decides each request with IAM on its
  concrete resource (`bus:Publish`/`bus:Consume` on the topic, `discovery:TriggerJob` on the job,
  `discovery:CancelJobRun` on the run, ...), so a Deny on one job or topic counts, within the module's broker
  grants (`broker_grants`, cached per principal until the store's revision changes). It aims schedules at the
  job's own trigger, sets a trigger's kind (`event` for the job's own module only) and TTL, scopes a trigger's
  `Nats-Msg-Id` to the caller and the job (JetStream dedups across the whole jobs stream: no module can make
  another's trigger a duplicate), and passes through the trace and claim-check headers only. Without an engine
  answering (a broker without the callout) the SDK does it itself, and remembers for a minute that none did.
  The job host decides that a lost run's trigger expired from the expiry it recorded (`trigger_expires_at`),
  not by reading the stream, and drops a trigger fired by another module's schedule (`Nats-Scheduler`).
- **Sealed triggers.** Every trigger, schedule and cancel the engine writes carries a seal (`Abi-Job-Seal`, an
  HMAC with a key in `IAMSecrets`, `iam/job-trigger-seal`) over where it is delivered, its kind, its body and its
  claim-check headers (`naas_abi_sdk.jobs.seal_fields`). A fired schedule copies the seal of its schedule
  message. A module's job host takes no trigger or cancel the engine did not seal: it asks the engine
  (`verify_trigger`), and drops the rest. This is what stops a message that lands under a trigger subject by a
  JetStream answer a module aimed there (see the remaining gap below). The SDK cannot verify an ES256
  signature itself (its workers carry no crypto library), hence a seal the engine checks.
- **Every responder answers only `_INBOX.` reply subjects** (`naas_abi_sdk.messages.reply_allowed`): the engine's
  services drop a request asking for any other reply subject before running it (`nats_tracing.traced_handler`),
  the SDK's hosts (agent, app, model hosts, app streams), discovery, transfer hosts and the broker control drop
  such a request before doing anything. A reply subject is the sender's choice, and the engine answering with
  its own rights on `$JS.API.STREAM.PURGE.<stream>` empties that stream (checked on a real server).
- **Remaining gap: JetStream answers with fixed content where a module asks.** The server answers a module's
  JetStream requests on the reply subject the module chose, with no permission check, and a stream captures
  what lands on its subjects. With direct gets taken away, what a module can still aim that way has content it
  does not choose: a pub ack (`{"stream":…,"seq":…}`, no headers), an acknowledgement's empty answer, a
  fetch from its own consumer (delivered under its original subject, so no consumer filtering another subject
  takes it, though a plain subscriber of the reply subject receives it). A job host drops such a trigger or
  cancel (unsealed). Another topic's queue can still store a pub ack or an empty message, and another module's
  subscriber can still receive one: bus messages are not authenticated. The JetStream API ignores such
  deliveries (no purge or delete, checked).
  - **Proposal, pending #44's acceptance:** NATS accounts for modules (modules in their own account, or one
    each, with JetStream and the kernel reached through service exports and imports, replies mapped back into
    the module's account). It would close this at the broker; it changes nats.conf in `abi dev`, the deploy
    templates and the demo, and needs cross-account pull consumers.
- **Upgrading remote modules.** A module on an SDK older than this change breaks behind the callout: it reads
  stream info, creates its consumers and streams, publishes its triggers and schedules into the jobs stream and
  reads claim checks by direct get, all refused now. Upgrade every remote module's `naas-abi-sdk` with the
  engine. Its jobs stream settings are the engine's (no `allow_rollup_hdrs` asked: the server sets it with
  schedules).
- **Quotas.** `ABI_CLAIM_CHECKS` has no size limit beyond its seven-day age, and the overflow host's 64 sessions
  and 1 GiB have no per-caller share: one module can fill either for everyone.
- **Verifiers** keep the keys they know for 15 minutes past their cache when the JWKS cannot be read, back off
  5 seconds between attempts, and fetch outside the lock every `verify` takes.
- **Manifests.** Approving or rejecting without a version decides the pending one only. A superseded version
  submitted again (a rollback) is pending again. `broker_permissions` reads policies from the store, never
  from the cache.
- **IAM changes reach other engines** on `abi.iam.v1.changed`. `abi iam` publishes it after each write. A
  connected module keeps its broker permissions until it reconnects. The SDK reconnects once its manifest is
  approved.
- **Not in this change.** Personal keys (`abi_pk_`) and token exchange (#62); moving Nexus's narrow tokens
  to the engine issuer; `nats_rpc` adapters logging in through the callout (they use the `engine` password).
