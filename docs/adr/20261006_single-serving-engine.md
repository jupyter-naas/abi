# One serving engine per NATS account, handed over by lease

## Status
Accepted (2026-10-06), implemented: see "Implementation status" below.
Follows the PR #1299 review (`REVIEW.md`, item 4). Extends the rollout model of
`20260923_module-discovery-registry.md` (rollouts and draining) to the engine.

## Date
2026-10-06

## Context
With a top-level `nats:` block, `EngineServiceLoader.load_services` loads every
`ON_DEMAND_SERVICES` entry, and `EngineNATSLoader` serves all of them on
queue-grouped subjects (`abi.svc.<service>.v1.*`). Every engine process started
from that config becomes an owner of every kernel service. With two of them, the
broker splits requests between two copies of each service:

- Services that keep state in the process diverge. A coding environment session
  created through one owner is NOT_FOUND on the other.
- Embedded stores (Oxigraph, Qdrant) hold file locks, so the second engine fails
  to start, or starts without them.
- DuckLake's `_CatalogLock` serializes access to a SQLite catalog within one
  process only.

`abi dev up --with-nats` avoids this by leaving Dagster out. Nothing else does:
`--service dagster`, a deploy that runs api and dagster from one config, a
second replica, or a script calling `Engine().load()`. Dagster is being retired.
A second serving engine should be impossible, not merely avoided.

Deploys must still have no downtime. A new engine that simply fails while the old
one runs deadlocks a rolling update: the new pod never becomes ready, so the old
one is never stopped. That is the same stall the module registry had before
rollouts. Stopping the old engine before starting the new one costs a full boot
(2 to 3 minutes for the API) on every deploy.

Kernel subjects carry no project, so two engines on one account conflict even if
their configs name different projects.

## Decision

### An ownership lease
Exactly one engine serves kernel services per NATS account. It proves this by
holding a lease: the key `owner` in the JetStream KV bucket `ABI_ENGINE` (history
1). The value describes the holder: engine instance id, host, pid, package
version, rollout id and start time.

- **Acquire** with an atomic `create`. Only one contender can win.
- **Renew** every `lease_seconds / 4` with `update(last=revision)`. Each renewal
  call is cut off after that same quarter period, so a hung call cannot delay
  fencing.
- **Release** on clean shutdown with `delete(last=revision)`.
- **Expiry is observed, not computed.** A contender that sees no new revision for
  a full `lease_seconds` on its own monotonic clock treats the holder as dead. It
  then takes the key by compare-and-swap on the revision it last saw. Clocks are
  never compared across hosts, and a holder that renews in time makes the takeover
  fail. Contenders watch the key, so a release is seen at once.

### Three roles
- **`serve`** (default): takes the lease, serves the kernel subjects and hosts
  the jobs.
- **`client`**: never takes the lease, serves nothing and hosts no jobs. It
  opens no backend: every service is a NATS client of the serving engine, the
  same facades a serving engine gives its modules. Only the model registry
  stays in the process, in memory, for modules to register their models. Its
  agents keep their memory in the serving engine's document service, and it
  leaves the ontologies to the serving engine, which owns the triple store. It
  is for scripts and notebooks that load the engine next to the serving one.
- **`auto`**: serves when no engine does and is a client otherwise. It never
  stands by. CLI commands that load an engine (`abi chat`, `abi agent list`,
  `abi run script`) use it unless `ABI_ENGINE_ROLE` is set, so they keep working
  next to a running stack and on their own.

Set with `nats.engine.role` in config, or `ABI_ENGINE_ROLE`, which wins.

### Starting a serving engine
The engine claims before it opens any backend, so a refused engine has no side
effects.

- **Lease free:** take it, open the backends, serve, then load modules. This is
  the order engines had before.
- **Lease held, with no rollout id or the holder's rollout id:** watch the key for
  up to one `lease_seconds`. If the holder renews, fail. A live holder renews
  every quarter period, so this takes seconds. The error names the holder's host,
  pid, version, rollout and start time. If it doesn't renew, the holder is dead:
  take over. A restart after a crash therefore still works, after at most one
  lease period. This rule is what makes Dagster, a second replica, a second
  `abi dev up` or a stray script fail.
- **Lease held, with a different rollout id (`ABI_ROLLOUT_ID`, as for modules):**
  stand by. Load services and modules, then return from `Engine.load` so the
  process reports ready. In NATS mode modules reach services through NATS
  clients, so they run against the serving engine. A standby opens its backends,
  which are shared (see below), but serves nothing and hosts no jobs until it
  takes the lease. Then it serves and starts the jobs. A standby that has not
  taken over within `standby_timeout_seconds` stops the process, so a deploy that
  never stops the old engine is visible.

### Handover
`Engine.shutdown` on the holder, as on `SIGTERM`:

1. It stops its jobs. They finish against the engine still serving: itself.
2. It releases the lease. The standby, watching the key, takes it and subscribes.
3. It ends its shared (queue-grouped) subscriptions, so new requests and new
   sessions go to the standby.
4. It answers the calls it has already received and keeps the sessions it owns
   until they finish, or until `drain_seconds` passes (default 60, a transfer's
   idle expiry). Then it closes what is left and its connections.

The standby subscribes while the old engine drains, so for a moment both serve:
an overlap rather than a gap. Shared backends make the overlap safe, including a
call the old engine finishes after the release.

### Calls already received
The kernel services' one-shot endpoints are NATS micro services. `nats.micro`'s
`Service.stop` unsubscribes: it cancels a handler still running and drops the
requests already delivered, whose callers then time out. So each kernel primary
(`nats_sessions.ServicePrimary`) counts the calls it has received as sessions. At
step 3 its endpoints stop taking calls; at step 4 it answers the ones it has.
Fencing and the drain deadline still cancel them.

A shared subscription is ended at the broker first: the UNSUB is written, then a
round trip confirms it (`nats_sessions.stop_delivery`). Only then is it drained.
nats-py's `Subscription.drain` alone writes its PING before its UNSUB, so a
request the broker routes in between arrives after the drain and is dropped
(reproduced with concurrent requests on nats-server 2.14, though not on every
run). Both pieces reach into nats-py and `nats.micro` internals; the real-broker
tests catch a change there.

### Sessions belong to one engine instance
Transfers, model streams and parked overflow replies live in one process. Their
later messages use subjects that carry an owner id
(`<prefix>.<owner>.<operation>`), so they reach that process only. Each engine
generates one instance id. The lease is held under it, and every session host the
engine starts takes it as the owner (`nats_sessions.owned_by`), so the lease
record names the process a session belongs to. A session in progress at the
handover goes on with the old engine on those subjects (step 4), while new ones
open on the standby.

### Standby needs shared backends
Zero-downtime deploys run on shared backends (PostgreSQL, S3, an Oxigraph or
Fuseki server, a Qdrant server), never on SQLite or embedded stores. This is
enforced. Each service's adapter configuration declares where its data lives
(`local_storage()`: a description when it stays on this host, `None` when every
engine reaches it). A serving engine started with a rollout id refuses to start,
before it opens any backend or touches the lease, if a service it owns keeps its
data in the process or on local disk (SQLite, embedded Oxigraph or Qdrant,
in-memory, a local filesystem). The error names each service and where its data
is. Those adapters stay valid for development and single-host setups, which
deploy without a rollout id.

- Only services the engine owns count: in NATS mode the on-demand services, those
  its modules need, and the coding environment and source control.
- The bus is not checked: in NATS mode it is the broker's JetStream.
- Secrets (`dotenv`, `base64`, `naas`) are deployment configuration, the same for
  every engine of a deploy, so they pass.
- A cache tier on `object_storage` or `keyvalue`, and a triple store on object
  storage, are as shared as the service they use.
- A `custom` adapter passes only with `shared_storage: true`.

### Retry when nobody answers
`NatsRPCClient` and the SDK `Transport` send a request again on
`NoRespondersError`, with a short backoff for up to 5 seconds
(`naas_abi_sdk.no_responders`), within the call's own deadline. This is always
safe, because nobody received the request. It hides the handover gap, and a
restart after a crash when it is short enough. A crash still loses the requests
the engine had already received: nobody knows whether they ran, so they are not
sent again and their callers time out.

Only subjects the engine serves on queue groups are retried: `abi.svc.*` and
`abi.discovery.<project>.v1.<operation>`. Presence, agent and transfer-session
subjects belong to one instance, and nobody answering there means it is gone, so
they still fail at once.

### Fencing
A holder that has not renewed for half a lease period stops serving at once. It
keeps renewing. If a renewal succeeds while the lease is still its own, it
serves again. If another engine holds the lease, the process stops (`SIGTERM`).
Since a contender waits a full lease period before taking over, the old holder
has stopped serving well before the new one starts. Fencing does not wait for
sessions: they close at once.

### Defaults
Under `nats.engine`: `role` `serve`, `rollout_id` empty, `lease_seconds` 20 (1 to
300), `standby_timeout_seconds` 900, `drain_seconds` 60 (0 closes the sessions at
once).

### Shape
A self-contained `naas_abi_core/engine/ownership/` domain:

- `ownership_ports.py`: `EngineLeasePort` (read, create, update and delete by
  revision, `wait_for_change`), `Holder`, `LeaseRecord`.
- `ownership_service.py`: `EngineOwnership`, the state machine (idle, standby,
  serving, fenced, lost, released) over any lease adapter.
- `adapters/secondary/`: `JetStreamLease` and `InMemoryLease`.
- `ownership_factory.py`: `this_process()` and `create_engine_ownership()`.
- `tests/lease__secondary_adapter__generic_test.py`: the contract every lease
  adapter runs.

`engine_loaders/EngineOwnershipLoader.py` runs it for the synchronous engine, on
its own event loop thread and NATS connection, so a busy service endpoint never
delays a renewal. `Engine.load` claims first; `Engine.shutdown` releases.

`engine/nats_sessions.py` holds the session side: `owned_by` (hosts built inside
take the engine's instance id), `SessionHost` (`stop_accepting`,
`sessions_finished`, `stop`), `ServicePrimary`, `stop_delivery` and
`wait_for_sessions`. `TransferHost` (and so the overflow host), the model
registry endpoint and every kernel primary are session hosts: `ServicePrimary`,
or `ServiceWithTransfers` for those that stream through a transfer host. A
primary's micro service (`nats_tracing.TracedService`) does the endpoint side:
`stop_accepting`, `requests_finished`, `stop`. `wait_for_sessions` waits twice,
because a call answered during the first wait can park its overflowing reply on
a host already done. A client engine's services come from
`EngineNATSDependencies.build_clients`.

## Consequences
- A second serving engine fails at start with a message naming the first. This
  includes a Dagster engine, which needs no special case. Dagster leaves the dev
  CLI and compose files when it is retired.
- **Deploys with no downtime run on shared backends only.** A rollout id combined
  with a local backend is rejected at config load, so this can't be set up by
  mistake. Development and single-host setups keep their local backends and deploy
  stop-then-start: without a rollout id, the new engine fails until the old one is
  gone.
- On Kubernetes:
  - Set `ABI_ROLLOUT_ID` per deploy, for example the image tag.
  - Use `maxSurge: 1` and `maxUnavailable: 0`.
  - Count a standby as ready.
  - Set `terminationGracePeriodSeconds` above the time jobs need to finish plus
    `drain_seconds`.
- A standby engine serves HTTP during the handover. Its modules and API routes
  use the NATS clients, so they reach the old engine until the switch.
- Migrations that run at boot must work with the previous release still serving
  (expand, then contract). The new version boots while the old one is live.
- Without a standby, failover after a crash takes up to one lease period plus a
  boot. A hot standby (same rollout, waiting instead of failing) would cut that,
  but it is left out of this decision.
- Platforms that keep the previous revision running for an unbounded time need
  one instance at most and must stop the previous revision. Otherwise the standby
  times out and fails.
- A one-off `auto` engine that finds the lease free serves until it exits. A
  serving engine started meanwhile without a new rollout id fails, naming it.
- Events and the activity log have shared adapters since
  `20261006_shared-event-and-activity-log-storage.md`: the activity log in the
  Document Service (the default), events on PostgreSQL.

## Implementation status
Done:
- The lease, the start rules, standby and takeover, fencing, release at shutdown,
  and the three roles. The CLI's engines use `auto`.
- Retry on "no responders" in both clients.
- The shared-backend check, declared by each service's adapter configuration.
- Shared storage for events (PostgreSQL) and the activity log (Document Service),
  so a deploy on shared backends passes the check.
- Tests:
  - The generic lease contract, run against the in-memory adapter and a real
    nats-server.
  - The state machine, the loader and the engine.
  - Where each adapter keeps its data.
  - Two real-broker runs under continuous traffic. A handover has zero failed
    calls. After a crash, every request sent after it is answered. Both tests
    fail when the retry is turned off.
- One engine instance id: the lease holder and the owner of every transfer,
  overflow reply and model stream the engine serves. A real-broker test opens a
  session on each host and finds the lease holder's id in every one.
- Sessions survive the release. Shutdown ends the shared subscriptions, waits
  for the engine's sessions up to `drain_seconds`, then closes them. Tested over
  a real broker, for a transfer host and for a whole engine: a transfer in
  progress at shutdown completes while new ones go elsewhere, and a stuck one is
  closed at the deadline.
- A `client` engine opens no backend. Tested over a real broker: it creates no
  file, never touches the lease, and every service is a NATS client.
- The calls already received are answered. Every kernel primary is a session
  host whose endpoints stop taking calls at the handover and answer the ones they
  have, within `drain_seconds`. Shared subscriptions end at the broker before
  they drain (`stop_delivery`), for the transfer hosts, the model registry and
  the discovery primary (`DiscoveryNATS.stop`) too.
  Tested over a real broker:
  - A call being handled and one queued behind it are answered while new calls
    reach the next engine. A call sent while nobody serves is answered by the
    next engine. A call still running at the deadline, or at fencing, is
    cancelled.
  - A queue member drained under load loses no request.
  - Key-value calls through the real primary run without pause across a deploy
    with no failed call.
  - A real engine answers a slow call in flight at shutdown, while new calls go
    to the next engine.

  With `nats.micro`'s own stop, the tests of calls received, of the deadline, of
  the deploy and of the engine fail.
  A unit test pins discovery's order (`stop_delivery`, then each drain).
