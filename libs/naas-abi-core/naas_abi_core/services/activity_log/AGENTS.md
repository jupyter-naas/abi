# Activity Log Service — AGENTS.md

> Scope: `libs/naas-abi-core/naas_abi_core/services/activity_log/`. Canonical reference for agents.

## Purpose

Thin domain wrapper that records `ActivityEvent`s per actor and supports filtered replay. **Recording failures are swallowed and logged** — activity logging must never break the call site that produced the event.

## Files

```
activity_log/
├── ActivityLogFactory.py
├── ActivityLogPort.py             # IActivityLogAdapter, IActivityLogDomain, DTOs
├── ActivityLogService.py          # public service
├── iam_catalog.py                 # the activity_log:* actions
├── adapters/activity_log_stream_codec.py   # event <-> protobuf, stream frames
├── adapters/secondary/
│   ├── ActivityLogDocumentAdapter.py   # default: the engine's Document Service
│   ├── ActivityLogSqliteAdapter.py
│   └── ActivityLogSqliteCopy.py        # job: copy SQLite logs into documents
└── tests/
    ├── activity_log__secondary_adapter__generic_test.py   # generic contract tests
    └── activity_log_authorization_test.py                 # IAM: in process and over NATS
```

## Port (`ActivityLogPort.py`)

Paging: events read back carry `seq` (store-assigned, increasing per actor;
ignored on `record`). `ActivityLogQuery(newest_first=True, before_seq=...,
after_seq=...)` pages with it: the last `seq` of a page is the next cursor. The
Nexus System app (Data tab) browses actors and their events read-only this way.

```python
class IActivityLogAdapter:
    def record(event: ActivityEvent) -> None
    def query(actor_id: str, query: ActivityLogQuery | None = None) -> list[ActivityEvent]
    def query_stream(actor_id, query=None)  # context manager -> Iterator[ActivityEvent]
    def list_actors() -> list[str]
    def shutdown() -> None

class IActivityLogDomain:    # same surface
    ...
```

## Service API (`ActivityLogService.py`)

```python
record(event)                            # swallows exceptions, logs warning
query(actor_id, query=None) -> list[ActivityEvent]
query_stream(actor_id, query=None)       # with ... as events: same filters, lazily
list_actors() -> list[str]
shutdown()                               # close adapter resources
```

### Streamed queries

`query_stream(actor_id, query)` reads what `query` returns, as the caller
iterates, inside the `with`. The
snapshot is pinned when the block opens (bounded below the actor's newest
`seq`), so events recorded while it is read are not included and the stream
always ends. The port's default (`paged_events`) reads `STREAM_PAGE` (500)
events at a time by keyset on `seq` (`after_seq`, or `before_seq` for
`newest_first`), honouring `limit`, and holds no lock between pages, so
`record` is never blocked by a reader. Over NATS the primary hosts `transfer/v1`
sessions on `abi.svc.activity_log.v1.transfer` (operation `query`, metadata a
`QueryRequest`, frames `ActivityEvents` batches of about 256 KiB built in
`adapters/activity_log_stream_codec.py`); the core client and the SDK facade
pin the snapshot before opening and have no unary fallback.

## Authorization

`ActivityLogService` checks every operation with IAM when it is wired with it
(an owner); a facade over NATS is not, and the owner it calls checks, as the
request's verified caller (the guard is described in
[`services/iam/AGENTS.md`](../iam/AGENTS.md), "Enforcing in a domain service").
An actor's log is the personal resource `actor/<principal id>` (opaque id,
platform-level, owner = the id): a role reaches it only through its owner, as
`actor/${principal.id}`. The other resource is the singleton `service/-`.
Levels: `ListActors` list; `Query`, `QueryStream` read; `Record` write;
`Shutdown` admin. Subjects are the operations under `abi.svc.activity_log.v1.`.

| Operation | Action | Resource |
|---|---|---|
| `record` | `activity_log:Record` | `actor/<the call's actor>` |
| `query` | `activity_log:Query` | `actor/<actor_id>` |
| `query_stream` | `activity_log:QueryStream` | `actor/<actor_id>` |
| `list_actors` | `activity_log:ListActors` | each actor listed |
| `shutdown` | `activity_log:Shutdown` | `service/-` |

- **The actor is the call's**, never the event's `actor_id`: the call's user,
  else the calling service account's name (`call_actor()`). The recorded event's
  `actor_id` is overwritten with it. An anonymous call records nothing.
- `record` still never raises: a denied or anonymous record is logged and dropped.
- Every user reads and records their own log through `builtin.self`.
- A caller who cannot see an actor gets `ResourceNotFoundError` (`NOT_FOUND`);
  one who can see it but not perform the action gets `PermissionDeniedError`
  (`PERMISSION_DENIED`).
- Over NATS, a streamed query first pins its snapshot with `query`, so it also
  needs `Query`.
- Nexus records one `http.request` per request inside the request's context
  (`api` on behalf of the signed-in user), so its actor is the user's id. A
  request with no signed-in user is recorded as `api`, with `anonymous: true`.
  Logs written earlier name actors `user:<id>` and `anonymous`.

## Available Adapters

| Adapter | Backend / Notes |
|---|---|
| `ActivityLogDocumentAdapter` (`adapter: document`, the default) | The engine's Document Service, namespace `naas_abi_core.services.activity_log`. Collections `events` (id `<actor_id>#<seq, 20 digits>`) and `actors`. Shared by every engine when the Document Service is on PostgreSQL. |
| `ActivityLogSqliteAdapter` (`adapter: sqlite`) | One SQLite DB file **per actor**, WAL mode, per-actor locking, LRU connection cache |

`ActivityLogDocumentAdapter` gets the Document Service through
`ActivityLogService.set_services` (`wire_services`), as cache tiers do. In NATS
mode that is the NATS facade. Each actor's `seq` is the next number after its
newest event, written create-only, and retried on conflict, so two engines
recording for one actor lose nothing.

## Copying the SQLite logs into documents

`ActivityLogDocumentAdapter.job_owners(services)` offers `activity_log_migrate`
(owner `naas_abi_core.activity_log`, `ActivityLogSqliteCopy.py`). The engine
hosts it in NATS mode, and a super admin runs it from the System app's Jobs
tab (Run now only).

- Payload: `{"data_dir": "storage/activity_log", "apply": false}`. The default
  is a dry run reporting, per actor, the events present in documents and the
  events missing. `data_dir` is relative to the engine's working directory and
  must resolve inside its `storage` directory (symlinks included).
- Events are recorded through `record` in SQLite order: new per-actor `seq`,
  after events recorded since the switch.
- Idempotent. A mark per (source directory, actor) in `sqlite_copies` keeps
  the last SQLite row handled; it is saved after each batch and after each
  refused event. Events written after the last mark are matched by content
  (type, timestamp, correlation id, attributes, counting identical events), so
  nothing is copied twice.
- Events whose values the Document Service refuses (checked with
  `validate_data` before `record`: non-finite numbers, integers above 64 bits,
  NUL characters) are skipped and listed in the result, by a dry run too. Any
  other error stops the run; running it again resumes.

## Factory (`ActivityLogFactory.py`)

```python
ActivityLogFactory.ActivityLogServiceSqlite(
    data_dir: str,
    synchronous: str = "NORMAL",
    journal_mode: str = "WAL",
    max_open_connections: int = 200,
    busy_timeout_ms: int = 5000,
) -> ActivityLogService
```

## Tests

```bash
uv run pytest libs/naas-abi-core/naas_abi_core/services/activity_log/ActivityLogPort_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/activity_log/ActivityLogService_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/activity_log/adapters/secondary/ActivityLogSqliteAdapter_test.py
# On SQLite documents, and on PostgreSQL documents with DOCUMENT_TEST_POSTGRES_DSN set:
uv run pytest libs/naas-abi-core/naas_abi_core/services/activity_log/adapters/secondary/ActivityLogDocumentAdapter_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/activity_log/adapters/secondary/ActivityLogSqliteCopy_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/activity_log/tests/activity_log__secondary_adapter__generic_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/activity_log/tests/activity_log_authorization_test.py --import-mode=importlib
```

## Adding a new adapter

1. Implement `IActivityLogAdapter` in `adapters/secondary/<Name>Adapter.py`.
2. Keep `record` **fail-open** — never raise out of the adapter into the service.
3. Run the generic contract tests against it (`tests/activity_log__secondary_adapter__generic_test.py`).
4. Add a `ActivityLogFactory.<Name>(...)` builder if there's a sensible default config.

## NATS RPC adapters

`adapters/primary/activity_log__primary_adapter__NATS.py` exposes the service's
protobuf endpoints. `adapters/secondary/ActivityLogSecondaryAdapterNATSClient.py` implements the outbound
port. Wire contracts live under `naas_abi_core/proto/activity_log/v1/`.

Every primary runs its domain call as the verified caller: it authenticates the
request with `nats_rpc.authenticate_request` (built on `engine/nats_identity.py`,
it answers a refusal itself) and hands that `CallContext`
(`engine/call_context.py`) to its dispatcher. The actor is the
token's identity; the user it acts for is named by the token itself: a
delegated token (`abi:delegated:agent`, `act` the acting service, `sub` the user)
made by IAM's token exchange, never a header (the old `Abi-On-Behalf-Of` header is
refused); trace and container come from the request's `context`. Never read identity from request fields
(`principal_id` and `tenant_id` are reserved). Clients of `api` and `engine` send a
delegation for the current call's user, and the call's trace and container. The domain service then authorizes the call (see "Authorization").

Clients inherit connection, JWT renewal, deadlines, and error handling from
`naas_abi_core.engine.nats_rpc.NatsRPCClient`; keep domain conversion and exception
mapping in the adapter. Primaries use `respond_protobuf` for bounded replies.
Requests and replies above the broker limit (8 MiB, or lower) overflow as
transfer frames up to 256 MiB; above
that, at the overflow host's capacity, or with an older peer, the call fails
with non-retryable `PAYLOAD_TOO_LARGE`. Micro-service error headers raise
instead of becoming an empty success. Overflowed values are held whole in
memory; results that should not be require streaming or a storage reference. No RPC is automatically replayed after transport failure:
a timeout can hide a completed operation. Reconcile its outcome before retrying.
`close()` releases only the client's transport, including for vector storage.

Run the colocated NATS tests with `--import-mode=importlib`; shared regressions
are in `engine/nats_rpc_test.py` and `engine/nats_rpc_integration_test.py`.
The latter uses a local `nats-server` executable without Docker.
