# jobs

## What it is
Utilities for declaring, scheduling, and triggering “jobs” (scheduled, manual, or event-driven work) backed by NATS JetStream schedules and subjects. It provides:
- Trigger types (`Cron`, `Every`, `OnEvent`)
- Job metadata (`JobDescriptor`)
- A decorator (`@job`) and mixin (`JobsMixin`) for module classes
- Client-side helpers to trigger and observe runs (`JobProxy`, `JobRun`)
- Context passed to handlers (`JobContext`)

## Public API

### Constants
- `JOB_CONTRACT_MAJOR`: Default contract major version (`1`)
- `RUN_STATUSES`: Possible run statuses
- `TERMINAL_STATUSES`: Terminal run statuses
- `MAX_TRIGGERS`: Maximum triggers per job (`16`)
- `TRIGGER_HEADER`: NATS header key used for job trigger source (`"Abi-Job-Trigger"`)

### Functions
- `go_duration_seconds(duration: str) -> float`  
  Parse a Go-style duration string (e.g. `"1h30m"`, `"1.5s"`) into seconds. Raises `ValueError` if invalid.
- `job(...)-> Callable`  
  Decorator to declare a job on a module method by attaching a `JobDescriptor` to it.
- `is_async_callable(handler: Any) -> bool`  
  Returns whether `handler` is an async callable.
- `stream_name(project: str) -> str`  
  Returns the JetStream stream name used for jobs in a project.
- `runs_collection(project: str) -> str`  
  Returns the document collection name used to store run records.
- `job_subjects(project: str, module_id: str, job_name: str) -> JobSubjects`  
  Build the NATS subjects used for trigger/schedule/cancel/consumer naming.
- `run_key(job_name: str, sequence: int) -> str`  
  Build a run id from job name and JetStream sequence number.

### Trigger types
- `Cron(expression: str, time_zone: str = "")`  
  6-field cron (seconds first) or an alias (e.g. `@daily`).  
  - `.headers() -> dict[str, str]`: NATS schedule headers
  - `.spec -> str`: normalized expression
- `Every(interval: str | timedelta)`  
  Fixed interval, stored as Go duration string; must be at least 1 second.  
  - `.headers() -> dict[str, str]`
  - `.spec -> str`
- `OnEvent(subject: str | None = None, *, event_type: str | None = None, filter: dict | None = None)`  
  Event trigger from a NATS subject or an ABI event type IRI (hashed to a subject).  
  - `.matches(data: Any) -> bool`: apply optional event filter
  - `.spec -> str`

Type alias:
- `Trigger = Cron | Every | OnEvent`

### Job metadata and retention
- `JobDescriptor`  
  Describes a job and its runtime constraints.
  - Fields: `name`, `description`, `triggers`, `max_concurrency`, `timeout`, `max_attempts`, `contract_major`
  - `.schedules -> tuple[Cron|Every, ...]`
  - `.events -> tuple[OnEvent, ...]`
  - `.to_pb() -> pb.JobDescriptor`
  - `JobDescriptor.from_pb(value: pb.JobDescriptor) -> JobDescriptor`
- `JobRetention`  
  Retention policy for finished run records (terminal statuses only).
  - Fields: `max_age`, `max_runs_per_job`, `skipped_max_age`, `interval`, `batch`

### Module integration
- `JobsNotHosted`  
  Raised when triggering jobs before a job host is bound (or after it stops).
- `JobsMixin`  
  Mixin for module classes to declare and expose jobs.
  - Class attributes:
    - `jobs: tuple[JobDescriptor, ...]` (explicit declarations)
  - Methods:
    - `expose_job(name: str, handler: Callable[..., Any]) -> None`  
      Bind a handler for a declared job name.
    - `missing_job_handlers() -> set[str]`  
      Job names without registered handlers.
    - `atrigger_job(name: str, payload: dict | None = None, *, idempotency_key: str | None = None) -> JobRun`  
      Async trigger for one of *this module’s* jobs (requires job host).
    - `trigger_job(name: str, payload: dict | None = None, *, idempotency_key: str | None = None, timeout: float = 30.0) -> JobRun`  
      Sync wrapper around `atrigger_job` (blocks; must not be called on the host loop).

### Handler context
- `JobContext`  
  Context passed to job handlers.
  - Fields: `run_id`, `job`, `attempt`, `trigger`, `payload`, `cancelled`, `logs`, `skipped`
  - `log(message: str) -> None`: bounded in-record logs
  - `skip(reason: str = "") -> None`: mark run as `SKIPPED` when handler returns

### Client-side job/run helpers
- `JobProxy`  
  Represents a job on another module (typically resolved via discovery).
  - `.name -> str`
  - `trigger(payload: dict | None = None, *, idempotency_key: str | None = None) -> JobRun`  
    Publishes a trigger to JetStream (manual trigger). Supports dedup via `idempotency_key`.
- `JobRun`  
  Handle to a triggered run.
  - `.run_id -> str`, `.duplicate -> bool`: `duplicate` is true when the trigger repeated an `idempotency_key` within the duplicate window (the first trigger's run, nothing stored)
  - `status() -> dict[str, Any]`: fetch run record (or `QUEUED` if not created yet)
  - `wait(*, timeout: float | None = None, poll_seconds: float = 0.5) -> dict[str, Any]`: poll until terminal status
  - `cancel() -> None`: cooperative cancel by publishing to the job’s cancel subject

## Configuration/Dependencies
- Depends on NATS JetStream at runtime for triggering/cancel (`transport.connect()`, `nc.jetstream().publish`).
- Uses document storage for run records via `naas_abi_sdk.services.document.DocumentService` and `DocumentClient` (lazily imported in `JobRun`).
- Event filtering uses `naas_abi_sdk.event_filter` (validation + matching).
- Trigger parsing/serialization uses protobuf types: `naas_abi_proto.discovery.v1.discovery_pb2` (`pb.JobDescriptor`, `pb.JobTrigger`).
- Tracing integration: `naas_abi_sdk.telemetry.client_span` (used in `JobProxy.trigger`).
- Large payload support uses `naas_abi_sdk.claim_check` (used in `JobProxy.trigger`).

## Usage

### Declare jobs on a module (decorator and/or descriptors)
```python
from datetime import timedelta
from naas_abi_sdk.jobs import JobsMixin, JobContext, job, Cron, Every, JobDescriptor

class MyModule(JobsMixin):
    jobs = (
        JobDescriptor("ingest", triggers=(Cron("0 0 6 * * *", time_zone="UTC"),)),
    )

    async def on_initialized(self):
        self.expose_job("ingest", self.ingest)

    async def ingest(self, ctx: JobContext) -> None:
        ctx.log("ingesting...")

    @job(triggers=(Every(timedelta(hours=1)),))
    async def summarize(self, ctx: JobContext) -> None:
        ctx.log("summarizing...")
```

### Trigger and wait on a job of another module (via `JobProxy`)
```python
import asyncio
from naas_abi_sdk.jobs import JobProxy, JobDescriptor

async def main(transport):
    descriptor = JobDescriptor(name="ingest")  # typically obtained via discovery
    jp = JobProxy(transport, project="myproj", module_id="module-123", descriptor=descriptor)

    run = await jp.trigger({"path": "naas/data.csv"}, idempotency_key="once")
    record = await run.wait(timeout=30)
    print(record["status"])

# asyncio.run(main(transport))
```

## Caveats
- `Cron` requires **6 fields** (seconds first) to match NATS schedules; aliases are restricted to: `@yearly`, `@annually`, `@monthly`, `@weekly`, `@daily`, `@midnight`, `@hourly`.
- `Every` must be **≥ 1 second**; `timedelta` inputs must be a whole number of seconds.
- `JobsMixin.trigger_job()` must **not** be called on the job host event loop; use `await atrigger_job()` there.
- `OnEvent` requires **exactly one** of `subject` or `event_type`.
- Job names must match the module’s name pattern (`[A-Za-z0-9_][A-Za-z0-9_.:-]{0,255}`) and be unique per module class.
