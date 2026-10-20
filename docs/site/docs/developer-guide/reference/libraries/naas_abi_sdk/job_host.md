# JobHost

## What it is

`naas_abi_sdk.job_host` runs a module’s jobs by:

- Creating/ensuring a JetStream stream and one durable pull consumer per job.
- Reconciling schedule triggers (`Cron` / `Every`) into scheduled JetStream messages.
- Bridging core-NATS events into durable job triggers.
- Executing job handlers with heartbeats, progress persistence, retries/backoff, and run record management.
- Periodically reaping “lost” runs and pruning old finished runs per retention.

## Public API

### Functions

- `scheduled_tick_ttl(trigger: Cron | Every) -> str`  
  Compute TTL for scheduled ticks so missed ticks don’t accumulate unboundedly.

- `ensure_stream(js: Any, project: str) -> None` *(async)*  
  Ensure the project jobs stream exists and has `allow_msg_schedules` and `allow_msg_ttl` enabled.

### Class: `JobHost`

#### Constructor

- `JobHost(transport, documents, module_id, project, handlers, *, instance_id="", heartbeat_seconds=10.0, ack_wait_seconds=30.0, fetch_timeout_seconds=1.0, backoff_base_seconds=5.0, max_backoff_seconds=300.0, close_grace_seconds=10.0, close_cancel_seconds=15.0, retention=JobRetention() | None, lost_after_seconds=300.0, completion_error_after_seconds=60.0)`

Key responsibilities controlled by parameters:

- Concurrency: `descriptor.max_concurrency` via JetStream `max_ack_pending` and an internal semaphore.
- Delivery timeout/renewal: `ack_wait_seconds` and periodic `msg.in_progress()` heartbeats.
- Retry/backoff: exponential backoff (`backoff_base_seconds`, `max_backoff_seconds`).
- Shutdown behavior: `drain()`, `close()` timing.
- Retention & upkeep: `retention`, `lost_after_seconds`.

#### Lifecycle

- `prepare() -> None` *(async)*  
  Ensure each job consumer exists (does not publish schedules or start consuming). Uses `DeliverPolicy.NEW` so only new triggers are delivered after consumer creation.

- `start() -> None` *(async)*  
  - Ensures the run-record collection exists (indexed `job`, `status`, `finished_at`).
  - Ensures stream and (re)adds consumers using this host’s config.
  - Reconciles schedules for each job.
  - Subscribes to event subjects and bridges them into triggers.
  - Starts pull-consumer loops and the upkeep loop.

- `drain(timeout: float) -> None` *(async)*  
  Stop pulling new jobs; allow already-started runs to continue up to `timeout`.

- `close() -> None` *(async)*  
  Cancel consumers and upkeep, unsubscribe, request all running jobs to cancel, then:
  - Wait `close_grace_seconds` for tasks to finish.
  - If still pending, cancel handler tasks and wait up to `close_cancel_seconds`.

#### Triggering and cancellation

- `trigger(name: str, payload: dict | None = None, *, idempotency_key: str | None = None) -> JobRun` *(async)*  
  Trigger one of this module’s jobs via `JobProxy`.

- `cancel(run_id: str) -> bool`  
  Signal cancellation for a locally running run (sets the run’s `JobContext.cancelled` flag). Returns `False` if not running on this host.

#### Upkeep / retention

- `reap_lost_runs(now: datetime | None = None) -> int` *(async)*  
  Mark certain stalled `RUNNING`/`RETRYING` runs as `FAILED` when nothing will finish them (e.g., host stopped and no attempts remain, or trigger TTL expired). Skips runs currently running on this host.

- `prune(now: datetime | None = None) -> int` *(async)*  
  Apply retention rules to delete old finished runs and enforce `max_runs_per_job` (up to `retention.batch` deletions per pass). No-op when `retention is None`.

#### Running a message (advanced)

- `handle(descriptor: JobDescriptor, handler: Any, msg: Any) -> None` *(async)*  
  Run a single delivery within a telemetry “consumer” span; delegates to internal delivery logic and records errors for non-success terminal statuses.

## Configuration/Dependencies

- **NATS JetStream**:
  - Stream name and subjects derived from `naas_abi_sdk.jobs.stream_name()` and `job_subjects()`.
  - Stream must support:
    - `allow_msg_schedules=True` (scheduled messages)
    - `allow_msg_ttl=True` (trigger TTL via `Nats-TTL`)
  - Consumers are durable pull consumers (`pull_subscribe_bind`), `AckPolicy.EXPLICIT`, `DeliverPolicy.NEW`, `max_deliver=-1`.

- **Documents service** (`documents`):
  - Must support: `ensure_collection`, `get`, `put`, `find`, `count`, `delete`.
  - Uses optimistic concurrency via `if_version` and handles `DocumentNotFound` / `VersionConflict`.

- **Claim check** (large messages):
  - Uses `naas_abi_sdk.claim_check` to resolve large incoming events and to publish large event-trigger bodies.

- **Telemetry**:
  - Uses `server_span`, `current_trace_id`, `record_error`.

## Usage

Minimal async skeleton (requires real `transport`, `documents`, and job descriptors/handlers from `naas_abi_sdk.jobs`):

```python
import asyncio
from naas_abi_sdk.job_host import JobHost
from naas_abi_sdk.jobs import JobDescriptor, Every

async def my_handler(ctx):
    ctx.logs.append("hello")
    return {"ok": True}

async def main(transport, documents):
    descriptor = JobDescriptor(
        name="example",
        max_concurrency=1,
        max_attempts=3,
        timeout=None,
        schedules=[Every(interval="60s")],
        events=[],
    )
    host = JobHost(
        transport=transport,
        documents=documents,
        module_id="mod_1",
        project="proj_1",
        handlers={"example": (descriptor, my_handler)},
        instance_id="instance-A",
    )

    await host.prepare()
    await host.start()

    # ... run until shutdown ...
    await host.drain(timeout=10)
    await host.close()

# asyncio.run(main(transport, documents))
```

## Caveats

- **At-least-once delivery**: triggers may be redelivered after crashes or missed acks.
- **Attempts vs deliveries**: “attempt” increments when the handler starts (run record exists and is updated), not per delivery; deliveries that can’t read/write the run record are `nak`’d with backoff and do not consume attempts.
- **Trigger TTL can prevent retries**: if a retry delay would extend beyond the message’s `Nats-TTL`, the run is marked `FAILED` instead of `RETRYING`.
- **Run IDs reuse stream sequences**: if the jobs stream is recreated, sequences can be reused; the host detects mismatched triggers and replaces old run records.
- **Retention does not delete active runs**: pruning applies to terminal statuses only; active runs are never pruned.
