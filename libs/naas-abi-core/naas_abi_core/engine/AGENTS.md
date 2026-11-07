# Engine - AGENTS.md

> Scope: `libs/naas-abi-core/naas_abi_core/engine/` (the engine process, its
> NATS runtime, its identity and its broker). Sub-scopes have their own guides:
> [`engine_loaders/AGENTS.md`](engine_loaders/AGENTS.md) (composition),
> [`ownership/AGENTS.md`](ownership/AGENTS.md) (the serving-engine lease). The policy
> engine itself is [`services/iam/AGENTS.md`](../services/iam/AGENTS.md); the sign-in
> side is [`services/identity/AGENTS.md`](../services/identity/AGENTS.md).

## Purpose

Who is calling, and what the broker lets each connection reach. The engine turns
verified credentials into a `CallContext` for every call a kernel service serves
(NATS, Nexus REST, in process), signs and verifies the engine's ES256 tokens,
answers the broker's auth callout, and writes the streams modules use. The
decisions themselves (policies, evaluation, roles, token claims and audiences) are
IAM's: this file covers how the engine carries identity and enforces the broker
side.

## Files

| File | Role |
|---|---|
| `call_context.py` | The caller identity of the call being served: re-exports the SDK types, `as_service_account`, `call_subject`, `vouched_by_first_party` |
| `call_context_types.py` | A verbatim copy of `naas_abi_sdk/call_context.py`, for a core installed without the SDK (a test keeps the two equal) |
| `nats_identity.py` | `caller_context`: the `CallContext` of a NATS request from its verified token; the only place a NATS primary builds one |
| `nats_auth.py` | ES256 engine tokens: `TokenVerifier`/`JWKSVerifier`, `TokenClaims`, audiences, `TokenSource`/`RenewingTokenSource`, service keys |
| `nats_credentials.py` | Where a core process's tokens and JWKS come from: the serving engine's own issuer, or a service key exchanged over NATS |
| `nats_auth_callout.py` | The broker's auth callout, answered by the serving engine |
| `nats_nkeys.py` | NATS nkeys and user JWTs for the callout |
| `nats_broker_control.py` | `abi.broker.v1.*`: the streams, consumers and job messages modules use, written by the engine |
| `nats_rpc.py`, `nats_dispatch.py`, `nats_tracing.py`, `nats_runtime.py` | The RPC transport (`authenticate_request`), per-primary worker capacity (`DomainRPCDispatcher`), traced micro services, the shared client |
| `nats_transfer.py`, `nats_overflow.py`, `nats_sessions.py` | Transfer sessions, RPC overflow host, session ownership at a handover |
| `nats_test_tokens.py`, `nats_test_server.py` | Engine tokens and a local `nats-server` for tests |
| `Engine.py`, `EngineProxy.py`, `IEngine.py` | The engine; `service_credentials(name, audience=)` gives a first-party account's token source |
| `engine_configuration/` | Pydantic configuration (`EngineConfiguration*`): the `nats`, `identity` and `services.iam` blocks included |
| `engine_loaders/` | Service, NATS, module and job loaders (see its guide) |
| `ownership/` | One serving engine per NATS account (see its guide) |

## The call context

`CallContext` is one context variable, defined in `naas_abi_sdk.call_context` and
re-exported here, so the engine and the SDK clients it runs read the same value. A
core installed without the SDK (no `nats` extra) runs `call_context_types.py`.

```python
@dataclass(frozen=True)
class Principal:
    id: str                         # usr_/grp_/sa_ id; "anonymous" for none
    kind: Literal["user", "service_account", "anonymous"]
    name: str | None = None         # service-account name, e.g. "api"
    issuer: str | None = None       # users: IdP issuer
    subject: str | None = None      # users: IdP sub
    groups: frozenset[str] = frozenset()

@dataclass(frozen=True)
class CallContext:
    principal: Principal                     # the actor
    on_behalf_of: Principal | None = None    # the user, when acting for one
    audience: str | None = None
    token_id: str | None = None              # jti, for audit
    token_issued_at: int | None = None       # iat: IAM refuses a token older than the revocation floor
    scope: tuple[Statement, ...] | None = None   # abi_scope narrowing
    container: str | None = None             # the container the call is made in (its name): a request input, not identity
    trace_id: str | None = None
    triggered_via: str | None = None         # "api", "cli", "configuration"...: stamped on events
    delegated_token: str | None = None       # a module host's delegation (a credential: never printed)
```

- **The call's user** is `on_behalf_of` when set, else `principal` when it is a user,
  else none (`CallContext.user`). Services use it wherever an operation concerns "the
  user": the activity actor, the forge or Coder user, the owner of a new personal
  resource (`call_context.call_subject`). It never comes from a request field.
- The default is `ANONYMOUS`, which every check denies.
- Helpers: `use_call_context(ctx)` (set and reset), `current_call_context()`,
  `as_service_account(name)` (core only: in process, logged; how boot, schedulers,
  jobs and Nexus housekeeping run. Remote code has no equivalent: it holds only its
  token), `vouched_by_first_party()` (the actor is `api` or `engine`, so its word about
  the user, such as a verified email, is trusted).
- Id convention: service accounts and users carry `sa_`/`usr_` ids once IAM assigns
  them; `Principal.name` is the account name (`api`, `engine`, `module/<project>/<id>`).
- The event actor fields (`actor_user_id`, `actor_container`, `triggered_via`) come
  from the call's user, `container` and `triggered_via`; the older
  `event_actor_*` / `agent_*` names are views of this context. Events recorded before
  container paths keep their `actor_workspace_id`, which is read but no longer written.
- `inside(container)` makes the calls of a block in a container (the SDK's
  `call_context.inside`, re-exported): what they create is placed there and their
  module scopes are named there. IAM checks the container is registered under that
  path (`IAMService.call_container`).

**Who sets it.** Every primary adapter sets it **only from verified credentials**:

| Caller | Source | Result |
|---|---|---|
| NATS (kernel services, discovery, module hosts, the SDK) | The `Nats-Auth-Token` header, verified against the JWKS for an audience the endpoint accepts (`nats_identity.caller_context`; `nats_rpc.authenticate_request` wraps it for `nats.micro` requests and answers a refusal `UNAUTHENTICATED`) | No `act`: principal = `sub`. With `act`: principal = `act.sub`, on behalf of = `sub`. Groups from IAM plus `grp`. Scope from `abi_scope`. |
| Nexus REST | The session cookie's `abi:session` identity, or a delegated token on routes that accept it | principal = `api`, on behalf of = the user. A request with no verified user (no session, a link token, a revoked session) runs as `ANONYMOUS`, never as `api`: a public route must never get Nexus's own rights. |
| Nexus calling remote agents and apps | An `abi:delegated:agent` token exchanged for the target | Sent in the `Nats-Auth-Token` header, and handed to the agent host in `SubmitRequest.delegated_token` for the run's downstream calls |
| In-process code | Inherits the caller's context. `asyncio.to_thread` copies it; executor submissions use `contextvars.copy_context().run` (`DomainRPCDispatcher.call` does); background tasks capture it at creation or use `as_service_account` | unchanged |
| The SDK module host | Sets the SDK context from the verified incoming invocation; downstream SDK calls send the delegation from that context | principal = the module's account, on behalf of = the user |

- **`DomainRPCDispatcher.call(fn, request, caller)`** runs the worker in a copy of the
  context holding the caller; discovery, the model registry and transfer sessions use it
  the same way. A transfer session runs as the caller who opened it and belongs to that
  actor acting for that user (the same actor for another user is refused); model registry
  chat streams follow the rule (`same_caller`). Overflow chunks carry their call's token,
  user, trace and container; a client stream captures its user once, when it opens.
  `nats_runtime.run_coro` schedules through `run_coroutine_threadsafe`, which copies the
  calling thread's context, so a sync caller keeps its identity.
- **Never from request-body fields.** `CallContext.principal_id` and `tenant_id` in the
  proto are reserved and ignored (servers ignore them, clients leave them empty).
  `CallContext.container` is the container the call is made in: an input like any
  other, which IAM checks against its registry. `CallContext.workspace_id`, which SDK
  0.2 sets, is refused when set (`nats_identity.WorkspaceIdRefusedError`,
  `INVALID_ARGUMENT`): this engine takes the container of a call instead. `HttpRequest.user_id`, `request.user_id` in
  `source_control` and `coding_environment`, the prompt preamble Nexus prepends for
  agents and any `X-User-*` header are not identity.
- **The `Abi-On-Behalf-Of` header is refused, not ignored.** A user is named by a
  delegated token only. A request that still carries the header fails as unauthenticated
  before the domain service, with its own message (`on-behalf-of refused: ...`) and a log
  line (a header naming a user can only narrow a call, so dropping it silently would widen
  it). The core RPC client and the SDK transport of `api` and `engine` send a delegation for
  the call's user; any other identity calls as itself.
- **Credentials never reach module code.** When Nexus forwards a request to a module
  (remote apps, the built-in IdP route), it forwards an allow-list of headers, never a
  deny-list: `Authorization`, `Cookie` (but the IdP route's own `Path=/idp` cookies),
  `X-Api-Key`, auth-proxy identity headers (`X-Amzn-Oidc-*`, `X-Auth-Request-*`,
  `X-Goog-Iap-Jwt-Assertion`) are dropped. A module learns who is calling only from the
  delegated token's verified claims.
- The event, vector_store and cache NATS endpoints call their domain services
  (`EventService`'s stored-level operations, `VectorStoreService`'s port-shaped methods,
  `CacheService`'s tier views), so the check in the domain service covers them.

## Tokens: signing, verification, sources

IAM signs (`services/iam/tokens.py`); the engine side is `nats_auth.py`. Claims,
audiences, lifetimes, rotation and revocation are in
[`services/iam/AGENTS.md`](../services/iam/AGENTS.md), "Tokens".

- **Verification.** `TokenVerifier.verify(token, at=)` checks the ES256 signature
  against the JWKS (`JWKSVerifier` caches it five minutes, refetches on an unknown `kid`
  at most every 30 seconds, keeps known keys 15 minutes past their cache when the JWKS
  cannot be read, backs off five seconds between attempts and fetches outside its lock),
  `iss`, `aud`, `exp`/`nbf` with 30 seconds of skew, and `exp - iat <= 600`. A retired
  key verifies a token stored before its retirement (`at=`), never one presented later.
  `for_audiences(...)` narrows a verifier to the audiences an endpoint accepts: kernel
  endpoints accept `KERNEL_AUDIENCES` (`abi:nats`, `abi:delegated:agent`); module hosts and
  discovery's `authorize_*` accept the host family (`abi:host:<sa>`).
- **Sources.** A process that calls holds a `TokenSource`: the serving engine's in-process
  issuer (`nats_credentials.issuer_source`; no NATS hop; it verifies against its own JWKS),
  or a service key exchanged at `abi.iam.v1.token` (modules, scripts, client-role engines;
  `RenewingTokenSource` renews at half the token's life). `token_for(user, recipient, scope)`
  is the delegation hook: it makes `abi:delegated:agent` tokens for the call's user, cached per
  user, scope and recipient (2048 at most), and a call that cannot get one fails rather than
  calling as the account alone, which would drop the user. The exchange runs outside the
  source's lock (it calls IAM, which calls with the source's own token).
- **Client-role engines and `nats_rpc` adapters** exchange the engine account's key:
  `nats.service_key`, else the one the serving engine keeps in the secret service
  (`iam/service-keys/engine`).
- **Host tokens.** A call to a module host (subjects `abi.agent.<project>.<sa>...`,
  `abi.mod.<project>.<sa>...`) carries a token of audience `abi:host:<sa>`, never the
  caller's `abi:nats` token: a host reads the token of every request and `api` may do
  everything, so a token that named no host could be replayed anywhere. Kernel services refuse
  host tokens. A module's key buys one per host (`TokenRequest.audience`; `Transport.call` reads
  the host from the subject); the serving engine signs `api`'s
  (`Engine.service_credentials("api", audience=host_audience(sa))`). A transport given bare
  tokens takes a `host_token` and refuses to call a host without one. The broker control stores,
  in every trigger and cancel, a host token of the verified caller addressed to the job's host
  (the module's account, else the engine's).
- **Every responder answers only `_INBOX.` reply subjects**
  (`naas_abi_sdk.messages.reply_allowed`): the engine's services drop a request asking for any
  other reply subject before running it (`nats_tracing.traced_handler`), and so do the SDK's
  hosts, discovery, transfer hosts and the broker control. A reply subject is the sender's
  choice, and the engine answering with its own rights on `$JS.API.STREAM.PURGE.<stream>` would
  empty that stream.

## The broker: auth callout and broker control

`nats.conf` (written by `abi dev`, the CLI deploy templates and
`.deploy/docker/nats/nats.conf`) declares `authorization { users, auth_callout { issuer,
auth_users } }` with **two static users that skip the callout**: `engine`, the engine's own
login, and `auth`, the callout responder's. There is no shared `abi` or `module` user.

- **Engine login.** `engine` may use every subject but `$SYS.>`: the API, Nexus and jobs run
  on it and use many subjects. It is not narrowed to the kernel subjects yet.
- **The callout** (`nats_auth_callout.py`, `nats.auth_callout` in the configuration:
  `nats_url` as user `auth`, `issuer_seed`, `user_ttl_seconds`). Every other connection logs in
  as user `sa` with a service key as its password; the broker asks `$SYS.REQ.USER.AUTH` and the
  responder checks the key and its principal (`IAMService.authenticate_key`: a revoked,
  expired or suspended one is refused at once), derives the subjects the account's policy allows
  (`broker_permissions`, see "Broker permissions" in `services/iam/AGENTS.md`) and answers with a
  user JWT signed by the account seed (`NATS_AUTH_CALLOUT_SEED`), valid five minutes by default
  (240 to 600 seconds), never past the key's expiry, **without response permissions**. Each
  request is answered on its own task.
- **Expiry and renewal.** nats-py closes a connection the broker expired instead of reconnecting
  it, so a transport logged in with a service key reconnects itself every two minutes
  (`renew_seconds`); the callout answers again with the subjects of the policy as it is then.
  Calls that start during the few milliseconds of a renewal wait for it; one in flight when it
  begins is lost, as in any reconnect. A revoked key, a suspended account or a narrowed manifest
  therefore reaches the broker within the user's life; services enforce every change at once, so
  the broker only narrows further. IAM changes reach other engines on `abi.iam.v1.changed`
  (`abi iam` publishes it after each write); a connected module keeps its broker permissions
  until it reconnects, and the SDK reconnects once its manifest is approved.
- **Inboxes.** A client's inbox prefix is `_INBOX.<key id>` (a subject token), so it reads no
  other's replies. Modules may also publish to `_INBOX.>` (app request bodies and run updates
  go to inboxes the module is handed).
- **Broker control** (`nats_broker_control.py`, `abi.broker.v1.<operation>`,
  `naas_abi_sdk.broker_control`). Behind the callout a module creates no stream or consumer
  (their subjects travel in the request body, which the broker never reads), gets no stream
  info (a subjects filter would list every module's subjects), writes nothing into the jobs
  stream (schedules make the server allow rollups there: one `Nats-Rollup: all` would purge every
  module's triggers) and reads claim checks only through the engine. It asks the engine with its
  token: `ensure_topic` (`bus:Publish`), `ensure_queue` (`bus:Consume`), `ensure_job`
  (`discovery:ListJobs`), `set_schedules` (`discovery:ScheduleJob`), `trigger`
  (`discovery:TriggerJob`), `cancel` (`discovery:CancelJobRun`), `ensure_claim_checks`,
  `read_claim_check`, `verify_trigger`. The engine decides each request with IAM on its concrete
  resource (a Deny on one job or topic counts), within the module's broker grants
  (`IAMService.broker_grants`, cached per principal until the store's revision changes), and does
  it over its own login: it aims schedules at the job's own trigger, sets a trigger's kind (`event`
  for the job's own module only) and TTL, scopes `Nats-Msg-Id` to the caller and the job (JetStream
  deduplicates across the whole jobs stream: no module can make another's trigger a duplicate), and
  passes through the trace and claim-check headers only. `engine` and `api` are not checked. The
  caller's credentials come as request headers; the engine verifies them and stores a host token in
  the trigger, so the job host authorizes the run against the caller as of when it was stored
  (`authorize_job`), never against a header the module wrote. Without an engine answering (a broker
  without the callout) the SDK does it itself and remembers for a minute that none did.
- **Who a run runs as.** A manual trigger `api` or `engine` stores for a user who may trigger the
  job also carries `Abi-Job-Delegation` (sealed): an `abi:delegated:agent` token for that user with
  the job's module as the actor and the caller's scope, minted by the engine (`_delegation`). The
  module's host runs the handler and its steps' functions under it once discovery allowed the
  trigger and named that user, and renews it through its key, up to 8 hours after the trigger; the
  run's journal, results and child runs stay the module's own. An engine module's job has no module
  account: its authorizer runs it as `job/<module_id>` for the user from the host token, in
  process (its calls over NATS carry the engine's delegation for the user, so there they are
  bounded by the engine and the user). A
  module's own trigger, a schedule or an event runs as the module alone: a module never hands a user
  to another, as with agents. A schedule's input is the schedule's body, validated (a JSON object of
  4 KiB at most) and sealed by the engine.
- **Sealed triggers.** Every trigger, schedule and cancel the engine writes carries a seal
  (`Abi-Job-Seal`, an HMAC over where it is delivered, its kind, its body, its claim-check headers
  and its delegation,
  with a key in `IAMSecrets`, `iam/job-trigger-seal`); a fired schedule copies its schedule's seal. A
  module's job host takes no trigger or cancel the engine did not seal: it asks `verify_trigger`
  and drops the rest, and fails closed (a trigger is redelivered, never run, when no engine answers;
  a cancel is dropped). This is what stops a message that lands under a trigger subject by a JetStream
  answer a module aimed there. The job host decides that a lost run's trigger expired from the expiry
  it recorded (`trigger_expires_at`), and drops a trigger fired by another module's schedule
  (`Nats-Scheduler`). The SDK cannot verify ES256 itself (no crypto library in its workers), hence a
  seal the engine checks.
- **Claim checks** travel under the scope they belong to: `abi.cc.t.<topic hash>.>` for a topic,
  `abi.cc.j.<project>.<module hash>.>` for a module's job triggers, in the stream `ABI_CLAIM_CHECKS`;
  checked against a SHA-256 in the reference.
- **The secret endpoint is an allowlist** (`secret_nats_contract.may_use`, in `get`, `set`, `remove`
  and `list`; `PERMISSION_DENIED`): `engine` reaches every name but the IdP's (`idp/...`), `idp` its
  own, a module the names under `<module id>/`, another service account `<name>/`, a user nothing. A
  name that is not a plain `a/b` (a dot segment, an empty one, a backslash, a percent escape, a
  control character) is refused to everyone but `engine`. The store it serves holds the ES256 private
  halves, the engine's service key, the job-trigger seal key and the dotenv with the broker passwords
  and every provider key: a module granted `secret:*` signs as nobody and logs in as nobody. See
  `services/secret/AGENTS.md`.
- **Logs hold no key.** The console sink sets loguru `diagnose=False, backtrace=False` (its defaults print the
  value of every variable on each frame of a traceback, a service key among them).
- **Upgrading remote modules.** A module on an SDK older than the engine breaks behind the callout:
  it reads stream info, creates its consumers and streams, publishes into the jobs stream and reads
  claim checks by direct get (all refused), and sends its own token to the hosts it calls (which
  discovery refuses). Upgrade every module's `naas-abi-sdk` with the engine.

**Known limits.** NATS accounts for modules (their own account with JetStream and the kernel
reached through exports and imports) are proposed, not built: today a JetStream answer lands on the
reply subject a module chose with fixed content (a pub ack, an empty acknowledgement, a fetch from
its own consumer); see "Known limits" in `services/iam/AGENTS.md`. `ABI_CLAIM_CHECKS` and the
overflow host have no per-caller quota.

## Configuration

```yaml
nats:
  nats_url: "nats://engine:{{ secret.NATS_ENGINE_PASSWORD }}@127.0.0.1:4222"
  # service_key: abi_sk_...   # a client-role engine's key; unset: the serving engine's, from the secret service
  auth_callout:
    nats_url: "nats://auth:{{ secret.NATS_AUTH_PASSWORD }}@127.0.0.1:4222"
    issuer_seed: "{{ secret.NATS_AUTH_CALLOUT_SEED }}"
    user_ttl_seconds: 300           # 240 to 600
  client_timeout_seconds: 10
services:
  iam: {...}                         # services/iam/AGENTS.md
identity: {...}                      # services/identity/AGENTS.md
```

`nats.jwt_secret` is retired and refused at load: the engine signs ES256 tokens with keys IAM holds,
and modules hold service keys (`ABI_SERVICE_KEY`; `ABI_SERVICE_TOKEN` and `NATS_JWT_SECRET` are gone).
The broker's passwords and the callout seed are generated into `.env` on first run.

## The raw-send rule

The broker's `max_payload` (8 MB in `nats.conf` and `abi dev`) counts the body **and** the header block;
nats-py only checks the body, and a message over the limit makes the server close the connection. Every
raw NATS send in core, the SDK and Nexus must therefore go through a size-aware path (RPC overflow in
`nats_rpc.py` and the SDK `transport.py`, transfer streams, claim checks, `messages.reply`) or be bounded
by construction. `nats_send_sites_test.py` lists every send (`REVIEWED`, with the reason it fits): a new
raw `publish`, `request`, `respond` or bucket write fails it until it is routed through one of those helpers
or added there with its reason.

## Decisions

**One CallContext, filled from verified credentials only.**
*Decision.* A single context variable, defined in the SDK, carries who acts and for whom. One shared helper
(`nats_identity`) builds it for NATS; Nexus middleware sets it per request (`api` on behalf of the signed-in user);
in-process code inherits it; work for no caller declares an identity (`as_service_account`). Identity never comes
from a request body. A user is named by a delegated token, never a header.
*Consequences.* A domain service reads who calls with `current_call_context()`, whatever the transport (a test
checks that every kernel service sees the same context in process, through the core client and through the SDK
transport). Events published for a NATS call carry the user the caller acted for and the container of the call. A
request with no verified user is anonymous and denied everywhere.

**The broker confines each module; the engine writes what a module could abuse.**
*Decision.* The broker has two static logins (`engine`, `auth`); everyone else is admitted by the auth callout with
subjects derived from the approved policy; streams, consumers and job messages are written by the engine; hosts see
host tokens only.
*Consequences.* A leaked module key exposes only that module's approved permissions. `nats.conf` carries the callout in
every template. Hosting subjects carry the account token, which callers read from discovery records. Broker permissions
lag policy by the callout user's life, which is why services enforce every change at once.

## Tests

```bash
uv run pytest libs/naas-abi-core/naas_abi_core/engine -q
uv run pytest libs/naas-abi-core/naas_abi_core/engine/nats_auth_test.py libs/naas-abi-core/naas_abi_core/engine/nats_identity_test.py libs/naas-abi-core/naas_abi_core/engine/nats_credentials_test.py -q
uv run pytest libs/naas-abi-core/naas_abi_core/engine/nats_auth_callout_test.py libs/naas-abi-core/naas_abi_core/engine/nats_auth_callout_integration_test.py -q
uv run pytest libs/naas-abi-core/naas_abi_core/engine/call_context_test.py libs/naas-abi-core/naas_abi_core/engine/call_context_integration_test.py -q
```

Tests that serve or call NATS endpoints use `nats_test_tokens.TEST_TOKENS` (`.verifier` for primaries,
`.source("api")` for clients, `.token("api")` for a raw header; `TestTokens()` is another issuer whose tokens fail
`TEST_TOKENS.verifier`). Broker suites need `nats-server` on `PATH` and skip without it (`ABI_REQUIRE_NATS_SERVER=1`,
set in CI, turns the skip into a failure). `call_context_integration_test.py` checks that every kernel service sees
the same context in process, through the core client and over NATS; `nats_auth_callout_integration_test.py` runs real
logins, renewals and revocations against a real broker.
