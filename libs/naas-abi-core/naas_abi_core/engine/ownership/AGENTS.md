# Engine ownership

## Purpose
In NATS mode, exactly one engine per NATS account serves the kernel services. It
holds a lease that it renews. A second engine fails at start, unless it belongs
to another deploy (`ABI_ROLLOUT_ID`): then it stands by and takes over when the
serving engine stops. Decision and rationale:
`docs/adr/20261006_single-serving-engine.md`.

No NATS import outside `adapters/secondary/lease_jetstream.py` and
`ownership_factory.py`.

## Files
| File | Role |
|---|---|
| `ownership_ports.py` | `EngineLeasePort`, `Holder`, `LeaseRecord`, `LeaseConflict`, `LeaseTaken` |
| `ownership_service.py` | `EngineOwnership` (the state machine), `OwnershipTiming`, `Claim`, `OwnershipState`, errors |
| `ownership_factory.py` | `this_process()`, `create_engine_ownership()` over JetStream |
| `adapters/secondary/lease_jetstream.py` | `JetStreamLease`: key `owner` in KV bucket `ABI_ENGINE` |
| `adapters/secondary/lease_memory.py` | `InMemoryLease`: tests, one event loop |
| `tests/lease__secondary_adapter__generic_test.py` | `GenericLeaseAdapterTest`, the adapter contract |

The engine side is `engine_loaders/EngineOwnershipLoader.py`. It runs the domain
on its own loop thread and NATS connection. `Engine.load` claims;
`Engine.shutdown` releases.

Around the lease, in the engine:
- **One instance id.** `Engine.instance_id` is generated once. The lease is held
  under it, and every session host the engine starts takes it as the owner in its
  subjects (`engine/nats_sessions.py`, `owned_by`): transfers, overflow replies,
  model streams.
- **Sessions outlive the release.** `Engine.shutdown` stops the jobs, releases,
  ends the shared (queue-grouped) subscriptions, then waits for each
  `SessionHost`'s sessions up to `nats.engine.drain_seconds` (60) before closing
  them. Fencing closes them at once.
- **A client engine opens nothing.** With role `client` (or `auto` next to a
  serving engine) every service comes from
  `EngineNATSDependencies.build_clients`: NATS clients only, no owner, no
  subscription, no ontology loading. Only the model registry stays local, in
  memory.

## Port
`EngineLeasePort` holds one record, written only by compare-and-swap. Revisions
are positive and only move forward; an absent record has revision 0.

- `read() -> LeaseRecord | None`
- `create(holder) -> revision`: raises `LeaseTaken` when held.
- `update(holder, revision) -> revision`: always moves the revision forward.
  Raises `LeaseConflict` at another revision or when absent.
- `delete(revision)`: raises `LeaseConflict` at another revision.
- `wait_for_change(revision, timeout) -> LeaseRecord | None`: returns as soon as
  the lease is no longer at `revision`, or the current record after `timeout`.

## Service API
`EngineOwnership(lease, me, OwnershipTiming(lease_seconds, standby_timeout_seconds))`

- `claim() -> Claim`: `SERVING`, `STANDBY` (only for a rollout id other than the
  holder's), or raises `EngineAlreadyServing`. A holder that stays silent for a
  full lease period is taken over.
- `wait_for_lease()`: from standby, serve once the holder releases or dies. Raises
  `StandbyTimedOut`, or `EngineAlreadyServing` if the lease goes to an engine of
  its own rollout.
- `keep(on_fenced=, on_restored=, on_lost=)`: renews every quarter period, with
  each call bounded. After half a period without a renewal it calls `on_fenced`
  (stop serving). A later successful renewal calls `on_restored`. When another
  engine holds the lease it calls `on_lost` and returns.
- `release()`: stops renewing and deletes the lease if it is still its own.
- `require_shared_backends(me, local_backends)`: a deploy (`me.rollout_id`)
  refuses to start when a service it owns keeps its data on this host. It raises
  `LocalBackendsCannotHandOver`, naming each service and where its data is. The
  engine gets `local_backends` from `EngineServiceLoader.local_backends()`, which
  asks each owned service's adapter configuration for its `local_storage()`.

Expiry is observed (a revision that does not move), never computed from
timestamps, so hosts' clocks are never compared.

## Adapters
- `JetStreamLease.open(nc, bucket="ABI_ENGINE")` creates the bucket (history 1)
  on first use. JetStream's "wrong last sequence" maps to `LeaseConflict`, whether
  nats-py raises `KeyWrongLastSequenceError` or `BadRequestError` 10071 (delete).
  `wait_for_change` uses a KV watch. A value it cannot parse reads as an unknown
  holder.
- `InMemoryLease`: an `asyncio.Condition` bound to the loop that first uses it.

## Factory
- `this_process(rollout_id, instance_id=None)` describes this process as a
  `Holder`: the engine's instance id (a new one without), host, pid,
  `naas-abi-core` version and UTC start time.
- `create_engine_ownership(nc, me, timing, bucket=)` builds `EngineOwnership`
  over `JetStreamLease`.

## Tests
```bash
cd libs/naas-abi-core
uv run pytest --import-mode=importlib naas_abi_core/engine/ownership \
  naas_abi_core/engine/engine_loaders/EngineOwnershipLoader_test.py \
  naas_abi_core/engine/engine_loaders/EngineOwnershipLoader_integration_test.py \
  naas_abi_core/engine/Engine_ownership_test.py \
  naas_abi_core/engine/nats_sessions_test.py \
  naas_abi_core/engine/Engine_handover_integration_test.py
```
The JetStream and integration tests need `nats-server` on `PATH` (with JetStream)
and skip without it. CI runs them in `.github/workflows/standalone_sdk.yml`.
`Engine_handover_integration_test.py` loads real engines: one instance id across
the lease and every session, a transfer completing during shutdown, a stuck one
closed at the drain deadline, and a client engine that creates no file.

## Adding a new adapter
1. Implement every method of `EngineLeasePort` in
   `adapters/secondary/lease_<name>.py`. Writes must be atomic compare-and-swap,
   and an update must move the revision forward even for the same holder.
2. Add `lease_<name>_test.py` beside it, subclassing `GenericLeaseAdapterTest`
   with an `open_lease()` async context manager that yields a lease on an empty
   store.
3. Build it from `ownership_factory.py`.
