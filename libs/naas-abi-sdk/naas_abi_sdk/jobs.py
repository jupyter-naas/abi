"""Module jobs: scheduled, manual and event-triggered work on JetStream.

Declare jobs like agents and run them in the module's own process::

    class ABIModule(BaseModule):
        jobs = (JobDescriptor("ingest", triggers=(Cron("0 0 6 * * *", time_zone="UTC"),)),)

        async def on_initialized(self):
            self.expose_job("ingest", self.ingest)

        @job(triggers=(Every("1h"),))
        async def summarize(self, ctx: JobContext) -> None: ...

A module triggers its own jobs once they are hosted: ``self.trigger_job(name,
payload, idempotency_key=...)`` from sync code, ``await self.atrigger_job(...)``
from async code.

A workflow is a job with a typed input and output whose handler checkpoints its
steps (``naas_abi_sdk.workflows``, docs/adr/20261025_durable-workflows-on-nats.md):
its descriptor has ``kind="workflow"`` and JSON Schemas. ``Cron``/``Every`` can carry
an ``input``, the schedule message body, delivered as the run's payload.

JetStream message schedules (NATS >= 2.12, time zones >= 2.14) produce the
triggers; one durable consumer per job hands each trigger to one replica. See
docs/adr/20261001_nats-jobs.md.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, ClassVar

from naas_abi_proto.discovery.v1 import discovery_pb2 as pb

from naas_abi_sdk import event_filter
from naas_abi_sdk.telemetry import client_span

JOB_CONTRACT_MAJOR = 1
MAX_TRIGGERS = 16
TRIGGER_HEADER = "Abi-Job-Trigger"
# Set on a schedule that has an input: a changed input is a changed schedule.
INPUT_HASH_HEADER = "Abi-Job-Input-Hash"
JOB_KINDS = ("job", "workflow")
# Descriptors travel in discovery's registry snapshot, which holds every module
# and is capped at 512 KiB: a schema, a trigger input and a whole descriptor are bounded.
MAX_SCHEMA_BYTES = 16 * 1024
MAX_TRIGGER_INPUT_BYTES = 4 * 1024
MAX_DESCRIPTOR_BYTES = 64 * 1024
_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.:-]{0,255}")
_CRON_ALIASES = {
    "@yearly",
    "@annually",
    "@monthly",
    "@weekly",
    "@daily",
    "@midnight",
    "@hourly",
}
_DURATION = re.compile(r"(?:\d+(?:\.\d+)?(?:ns|us|µs|ms|s|m|h))+")
_UNIT_SECONDS = {
    "ns": 1e-9,
    "us": 1e-6,
    "µs": 1e-6,
    "ms": 1e-3,
    "s": 1,
    "m": 60,
    "h": 3600,
}

RUN_STATUSES = (
    "QUEUED",
    "RUNNING",
    "RETRYING",
    "SUCCEEDED",
    "SKIPPED",
    "FAILED",
    "TIMED_OUT",
    "CANCELLED",
)
# SKIPPED: the handler said the run had nothing to do (``ctx.skip``).
TERMINAL_STATUSES = ("SUCCEEDED", "SKIPPED", "FAILED", "TIMED_OUT", "CANCELLED")


def _hash(*values: str) -> str:
    return hashlib.sha256(json.dumps(values, ensure_ascii=True).encode()).hexdigest()


def _canonical(value: Any) -> str:
    """Stable JSON: the same value is the same bytes on every replica."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _normalize_input(value: dict[str, Any] | None) -> dict[str, Any] | None:
    """A trigger's input as a plain JSON object, or None (empty is no input)."""
    if not value:
        return None
    if not isinstance(value, dict):
        raise TypeError("A trigger input must be a dict (a JSON object)")
    try:
        encoded = _canonical(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"A trigger input must be JSON: {exc}") from exc
    if len(encoded.encode()) > MAX_TRIGGER_INPUT_BYTES:
        raise ValueError(
            f"A trigger input is at most {MAX_TRIGGER_INPUT_BYTES} bytes of JSON"
        )
    return json.loads(encoded)


def schema_json(value: dict[str, Any] | str | None, what: str = "schema") -> str:
    """A JSON Schema (a JSON object) as the canonical string a descriptor holds."""
    if value is None or value == "":
        return ""
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
        encoded = _canonical(parsed)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"The {what} must be a JSON Schema object: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"The {what} must be a JSON Schema object")  # noqa: TRY004 - one error for any bad schema
    if len(encoded.encode()) > MAX_SCHEMA_BYTES:
        raise ValueError(
            f"The {what} is {len(encoded.encode())} bytes; at most "
            f"{MAX_SCHEMA_BYTES} (keep descriptors small, link to docs for the rest)"
        )
    return encoded


def go_duration_seconds(duration: str) -> float:
    """Seconds in a Go duration (``"1h30m"``, ``"1.5s"``), as NATS headers write them."""
    if not isinstance(duration, str) or not _DURATION.fullmatch(duration):
        raise ValueError(f"Not a Go duration: {duration!r}")
    return sum(
        float(n) * _UNIT_SECONDS[u]
        for n, u in re.findall(r"(\d+(?:\.\d+)?)(ns|us|µs|ms|s|m|h)", duration)
    )


# --- triggers -------------------------------------------------------------------------


class _ScheduleInput:
    """The input a schedule carries: its message body, the run's payload."""

    input: dict[str, Any] | None

    @property
    def input_json(self) -> str:
        return _canonical(self.input) if self.input else ""

    @property
    def body(self) -> bytes:
        return self.input_json.encode() if self.input else b"{}"

    @property
    def input_hash(self) -> str:
        return hashlib.sha256(self.input_json.encode()).hexdigest()[:32]

    def _input_headers(self) -> dict[str, str]:
        # Only with an input: a schedule written before inputs existed (no
        # header) stays the same schedule, and its interval keeps running.
        return {INPUT_HASH_HEADER: self.input_hash} if self.input else {}


@dataclass(frozen=True)
class Cron(_ScheduleInput):
    """6-field cron with seconds (``"0 30 9 * * mon-fri"``) or an alias (``"@daily"``).

    ``input`` (a JSON object, at most 4 KiB) is each tick's payload. Changing it
    changes the schedule, which is published again."""

    expression: str
    time_zone: str = ""
    input: dict[str, Any] | None = field(default=None, hash=False)
    kind = "cron"

    def __post_init__(self) -> None:
        expression = self.expression.strip()
        if expression.startswith("@"):
            if expression not in _CRON_ALIASES:
                raise ValueError(f"Unknown cron alias: {self.expression!r}")
        elif len(expression.split()) != 6:
            raise ValueError(
                "Cron needs 6 fields (seconds first), as NATS schedules do"
            )
        object.__setattr__(self, "input", _normalize_input(self.input))

    @property
    def spec(self) -> str:
        return self.expression.strip()

    def headers(self) -> dict[str, str]:
        headers = {"Nats-Schedule": self.spec}
        if self.time_zone:
            headers["Nats-Schedule-Time-Zone"] = self.time_zone
        return {**headers, **self._input_headers()}


@dataclass(frozen=True, init=False)
class Every(_ScheduleInput):
    """Fixed interval, as a Go duration (``"1h30m"``) or a timedelta; at least 1s.

    ``input`` is as for ``Cron``."""

    interval: str
    input: dict[str, Any] | None = field(default=None, hash=False)
    kind = "every"

    def __init__(
        self, interval: str | timedelta, *, input: dict[str, Any] | None = None
    ):
        if isinstance(interval, timedelta):
            seconds = interval.total_seconds()
            if seconds < 1 or seconds != int(seconds):
                raise ValueError("Every needs a whole number of seconds, at least 1")
            interval = f"{int(seconds)}s"
        if go_duration_seconds(interval) < 1:
            raise ValueError("NATS schedules fire at most once per second")
        object.__setattr__(self, "interval", interval)
        object.__setattr__(self, "input", _normalize_input(input))

    @property
    def spec(self) -> str:
        return self.interval

    @property
    def time_zone(self) -> str:
        return ""

    def headers(self) -> dict[str, str]:
        return {"Nats-Schedule": f"@every {self.interval}", **self._input_headers()}


@dataclass(frozen=True, init=False)
class OnEvent:
    """Run on events: an ABI event type IRI or any NATS subject (core NATS).

    ``filter`` keeps irrelevant events from triggering the job: an
    EventBridge-style dict on the event's fields (``naas_abi_sdk.event_filter``),
    e.g. ``{"prefix": {"prefix": "naas/"}}`` for object puts under ``naas/``.
    """

    subject: str
    filter: dict[str, Any] | None = field(default=None, hash=False)
    kind = "event"

    def __init__(
        self,
        subject: str | None = None,
        *,
        event_type: str | None = None,
        filter: dict[str, Any] | None = None,
    ):
        if (subject is None) == (event_type is None):
            raise ValueError("OnEvent needs exactly one of subject or event_type")
        if event_type is not None:
            subject = f"evt.{hashlib.sha256(event_type.encode()).hexdigest()[:32]}.>"
        object.__setattr__(self, "subject", subject)
        object.__setattr__(
            self, "filter", event_filter.validate(filter) if filter else None
        )

    def matches(self, data: Any) -> bool:
        """Whether this event (its decoded JSON) should trigger the job."""
        return event_filter.matches(data, self.filter)

    @property
    def spec(self) -> str:
        return self.subject

    @property
    def time_zone(self) -> str:
        return ""


Trigger = Cron | Every | OnEvent


def _trigger_from_pb(value: pb.JobTrigger) -> Trigger:
    scheduled_input = json.loads(value.input) if value.input else None
    if value.kind == "cron":
        return Cron(value.spec, time_zone=value.time_zone, input=scheduled_input)
    if value.kind == "every":
        return Every(value.spec, input=scheduled_input)
    if value.kind == "event":
        return OnEvent(
            value.spec, filter=json.loads(value.filter) if value.filter else None
        )
    raise ValueError(f"Unknown job trigger kind: {value.kind!r}")


# --- descriptors ----------------------------------------------------------------------


@dataclass(frozen=True)
class JobDescriptor:
    """A job, or (``kind="workflow"``) a job with a typed input and output.

    ``input_schema`` and ``output_schema`` are JSON Schema objects as canonical
    strings (``schema_json``): at most 16 KiB each, and the whole descriptor at
    most 64 KiB, because discovery's registry snapshot holds every module."""

    name: str
    description: str = ""
    triggers: tuple[Trigger, ...] = ()
    max_concurrency: int = 1
    timeout: timedelta | None = None
    max_attempts: int = 1
    contract_major: int = JOB_CONTRACT_MAJOR
    kind: str = "job"
    input_schema: str = ""
    output_schema: str = ""

    def __post_init__(self) -> None:
        if not _NAME.fullmatch(self.name):
            raise ValueError(f"Invalid job name: {self.name!r}")
        if not 0 < self.max_concurrency <= 64:
            raise ValueError("max_concurrency must be between 1 and 64")
        if not 0 < self.max_attempts <= 100:
            raise ValueError("max_attempts must be between 1 and 100")
        if self.timeout is not None and self.timeout.total_seconds() <= 0:
            raise ValueError("timeout must be positive")
        if len(self.triggers) > MAX_TRIGGERS:
            raise ValueError(f"At most {MAX_TRIGGERS} triggers per job")
        if self.kind not in JOB_KINDS:
            raise ValueError(f"Job kind must be one of {JOB_KINDS}, not {self.kind!r}")
        object.__setattr__(self, "triggers", tuple(self.triggers))
        object.__setattr__(
            self, "input_schema", schema_json(self.input_schema, "input schema")
        )
        object.__setattr__(
            self, "output_schema", schema_json(self.output_schema, "output schema")
        )
        size = self.to_pb().ByteSize()
        if size > MAX_DESCRIPTOR_BYTES:
            raise ValueError(
                f"Job {self.name!r} describes itself in {size} bytes; "
                f"at most {MAX_DESCRIPTOR_BYTES}"
            )

    @property
    def is_workflow(self) -> bool:
        return self.kind == "workflow"

    @property
    def schedules(self) -> tuple[Cron | Every, ...]:
        return tuple(t for t in self.triggers if isinstance(t, (Cron, Every)))

    @property
    def events(self) -> tuple[OnEvent, ...]:
        return tuple(t for t in self.triggers if isinstance(t, OnEvent))

    def to_pb(self) -> pb.JobDescriptor:
        return pb.JobDescriptor(
            name=self.name,
            description=self.description,
            contract_major=self.contract_major,
            triggers=[
                pb.JobTrigger(
                    kind=t.kind,
                    spec=t.spec,
                    time_zone=t.time_zone,
                    filter=json.dumps(t.filter, sort_keys=True)
                    if isinstance(t, OnEvent) and t.filter
                    else "",
                    input=t.input_json if isinstance(t, (Cron, Every)) else "",
                )
                for t in self.triggers
            ],
            max_concurrency=self.max_concurrency,
            max_attempts=self.max_attempts,
            timeout_seconds=self.timeout.total_seconds() if self.timeout else 0.0,
            kind=self.kind,
            input_schema=self.input_schema,
            output_schema=self.output_schema,
        )

    @classmethod
    def from_pb(cls, value: pb.JobDescriptor) -> JobDescriptor:
        return cls(
            name=value.name,
            description=value.description,
            triggers=tuple(_trigger_from_pb(t) for t in value.triggers),
            max_concurrency=value.max_concurrency,
            timeout=timedelta(seconds=value.timeout_seconds)
            if value.timeout_seconds
            else None,
            max_attempts=value.max_attempts,
            contract_major=value.contract_major,
            # A descriptor written before the field existed has none: a job.
            kind=value.kind or "job",
            input_schema=value.input_schema,
            output_schema=value.output_schema,
        )


def process_workflow_name(kind: str, name: str) -> str:
    """The durable workflow of a ``Workflow`` or ``Pipeline`` class:
    ``workflow.greet``, ``pipeline.ingest``, as core names its bridged classes.

    Derived, so it is stable across restarts and replicas; a slug is lowercase
    ASCII, digits and ``_`` (no ``:``, which run ids use as their separator).
    """
    return f"{kind}.{name}"


@dataclass(frozen=True)
class JobSettings:
    """How the durable workflow of a ``Workflow`` or ``Pipeline`` class runs
    (``Process.job``).

    Every such class is a workflow that callers start by name; declaring
    ``job`` adds schedules or events (``triggers``) and sets its limits.
    Defaults are ``@workflow``'s.
    """

    triggers: tuple[Trigger, ...] = ()
    timeout: timedelta | None = None
    max_attempts: int = 1
    max_concurrency: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "triggers", tuple(self.triggers))
        # The descriptor's own checks (ranges, trigger count), at declaration.
        self.descriptor("check")

    def descriptor(self, name: str, description: str = "") -> JobDescriptor:
        return JobDescriptor(
            name=name,
            description=description,
            triggers=self.triggers,
            max_concurrency=self.max_concurrency,
            timeout=self.timeout,
            max_attempts=self.max_attempts,
        )


JobHandler = Callable[["JobContext"], Awaitable[Any]]


@dataclass(frozen=True)
class JobRetention:
    """How long a job host keeps finished run records (QUEUED, RUNNING and
    RETRYING runs are never touched). Each pass deletes at most ``batch``."""

    max_age: timedelta = timedelta(days=7)
    max_runs_per_job: int = 1000
    # Runs that did nothing (``ctx.skip``): polls would drown the history.
    skipped_max_age: timedelta = timedelta(hours=1)
    interval: timedelta = timedelta(minutes=10)
    batch: int = 200

    def __post_init__(self) -> None:
        if self.max_runs_per_job < 1 or self.batch < 1:
            raise ValueError("max_runs_per_job and batch must be at least 1")
        for value in (self.max_age, self.skipped_max_age, self.interval):
            if value.total_seconds() <= 0:
                raise ValueError("Retention durations must be positive")


def job(
    name: str | None = None,
    description: str = "",
    *,
    triggers: tuple[Trigger, ...] = (),
    max_concurrency: int = 1,
    timeout: timedelta | None = None,
    max_attempts: int = 1,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Declare and bind a job on a module method (``async def m(self, ctx)``).

    SDK modules require async methods; core engine modules also accept sync ones
    (run in a worker thread). The module class checks this when it is defined.
    """

    def decorate(method: Callable[..., Any]) -> Callable[..., Any]:
        doc = inspect.getdoc(method) or ""
        method.__abi_job__ = JobDescriptor(  # type: ignore[attr-defined]
            name=name or method.__name__,
            description=description or (doc.splitlines()[0] if doc else ""),
            triggers=tuple(triggers),
            max_concurrency=max_concurrency,
            timeout=timeout,
            max_attempts=max_attempts,
        )
        return method

    return decorate


def is_async_callable(handler: Any) -> bool:
    return inspect.iscoroutinefunction(handler) or (
        callable(handler) and inspect.iscoroutinefunction(type(handler).__call__)
    )


class JobsNotHosted(RuntimeError):
    """A module's jobs are triggered before (or after) its job host runs."""


class JobsSealed(RuntimeError):
    """A job is declared after the module's jobs were handed to its job host."""


class NonRetryable(Exception):
    """Raised by a handler for a failure another attempt cannot fix (a bad
    input, a result over its cap): the run fails at once, whatever attempts
    ``max_attempts`` leaves."""


class JobsMixin:
    """Job declarations for a module class: ``jobs``, ``@job`` methods, ``expose_job``.

    Shared by SDK modules (async handlers only) and core engine modules
    (``_sync_jobs = True``: sync handlers are allowed and run in a worker thread).
    """

    jobs: tuple[JobDescriptor, ...] = ()
    # job name -> method name, for jobs declared with @job (filled per subclass).
    _decorated_jobs: ClassVar[dict[str, str]] = {}
    _sync_jobs: ClassVar[bool] = False

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        decorated = {
            attr.__abi_job__.name: (attr_name, attr)
            for attr_name, attr in vars(cls).items()
            if hasattr(attr, "__abi_job__")
        }
        if not cls._sync_jobs:
            sync = sorted(
                n for n, (_, m) in decorated.items() if not is_async_callable(m)
            )
            if sync:
                raise TypeError(f"@job methods must be async on {cls.__name__}: {sync}")
        declared = list(cls.jobs)
        for _, method in decorated.values():
            if not any(j is method.__abi_job__ for j in declared):
                declared.append(method.__abi_job__)
        names = [j.name for j in declared]
        duplicates = sorted({n for n in names if names.count(n) > 1})
        if duplicates:
            raise ValueError(f"Duplicate job names on {cls.__name__}: {duplicates}")
        cls.jobs = tuple(declared)
        inherited = dict(getattr(cls, "_decorated_jobs", {}))
        inherited.update(
            {name: attr_name for name, (attr_name, _) in decorated.items()}
        )
        cls._decorated_jobs = inherited

    @property
    def _job_handlers(self) -> dict[str, Callable[..., Any]]:
        """Bound handlers by job name; @job methods are bound on first access."""
        handlers = self.__dict__.get("_abi_job_handlers")
        if handlers is None:
            handlers = {}
            for name, attr_name in self._decorated_jobs.items():
                bound = getattr(self, attr_name)
                spec = getattr(bound, "__abi_workflow__", None)
                if spec is not None:  # @workflow: validated input, typed output
                    from naas_abi_sdk.workflows import workflow_handler

                    bound = workflow_handler(bound, spec)
                handlers[name] = bound
            self.__dict__["_abi_job_handlers"] = handlers
        return handlers

    def expose_job(self, name: str, handler: Callable[..., Any]) -> None:
        """Bind a job handler during on_initialized, before readiness."""
        if not any(j.name == name for j in self.jobs):
            raise ValueError(f"Declare a JobDescriptor named {name!r} in jobs first")
        if name in self._job_handlers:
            raise ValueError(f"Job handler already registered: {name}")
        if not (is_async_callable(handler) or (self._sync_jobs and callable(handler))):
            raise TypeError("Job handler must be an async callable taking a JobContext")
        self._job_handlers[name] = handler

    def declare_job(
        self, descriptor: JobDescriptor, handler: Callable[..., Any]
    ) -> None:
        """Declare a job and bind its handler at runtime, for jobs that are not
        known when the class is written (core's Workflow/Pipeline bridge).

        Declare before the module's jobs go to its job host: SDK modules in
        ``on_load`` (the descriptor discovery shows is taken after it), engine
        modules before their host starts. Replicas must declare identical sets:
        discovery refuses a replica whose jobs differ. ``JobsSealed`` afterwards.
        """
        if self.__dict__.get("_abi_jobs_sealed"):
            raise JobsSealed(
                f"{type(self).__name__}'s jobs already went to its job host: "
                "declare jobs earlier (on_load, or before the host starts)"
            )
        if any(j.name == descriptor.name for j in self.jobs):
            raise ValueError(
                f"Duplicate job names on {type(self).__name__}: {descriptor.name}"
            )
        if not (is_async_callable(handler) or (self._sync_jobs and callable(handler))):
            raise TypeError("Job handler must be an async callable taking a JobContext")
        self.__dict__["jobs"] = (*self.jobs, descriptor)
        self._job_handlers[descriptor.name] = handler

    def declare_workflow(
        self,
        name: str,
        handler: Callable[..., Any],
        *,
        input_type: Any = None,
        output_type: Any = None,
        input_schema: dict[str, Any] | str | None = None,
        output_schema: dict[str, Any] | str | None = None,
        description: str = "",
        triggers: tuple[Trigger, ...] = (),
        max_concurrency: int = 1,
        timeout: timedelta | None = None,
        max_attempts: int = 1,
    ) -> JobDescriptor:
        """``declare_job`` for a workflow: ``async handler(ctx, inp)``, with the
        schemas of ``input_type``/``output_type`` (pydantic v2 models, duck-typed)
        or explicit ``input_schema``/``output_schema`` for dicts. Returns the descriptor."""
        from naas_abi_sdk.workflows import declare_workflow

        return declare_workflow(
            self,
            name,
            handler,
            input_type=input_type,
            output_type=output_type,
            input_schema=input_schema,
            output_schema=output_schema,
            description=description,
            triggers=triggers,
            max_concurrency=max_concurrency,
            timeout=timeout,
            max_attempts=max_attempts,
        )

    def _seal_jobs(self) -> None:
        """Runtimes call it as they hand the jobs to the job host."""
        self.__dict__["_abi_jobs_sealed"] = True

    def missing_job_handlers(self) -> set[str]:
        return {j.name for j in self.jobs} - set(self._job_handlers)

    def workflow_spec(self, name: str) -> Any:
        """The ``WorkflowSpec`` (input and output types) of one of this module's workflows."""
        specs = self.__dict__.get("_abi_workflow_specs", {})
        if name in specs:
            return specs[name]
        attr_name = self._decorated_jobs.get(name)
        spec = (
            getattr(getattr(self, attr_name), "__abi_workflow__", None)
            if attr_name
            else None
        )
        if spec is None:
            raise ValueError(f"{type(self).__name__} has no workflow named {name!r}")
        return spec

    # A module's own triggers go through its job host, on the host's loop.

    def _bind_job_host(self, host: Any, loop: asyncio.AbstractEventLoop | None) -> None:
        """Set by the runtime once the host started (``None`` once it stopped)."""
        self.__dict__["_abi_job_host"] = (host, loop) if host is not None else None
        if host is not None:
            self._seal_jobs()

    def _job_host(self) -> tuple[Any, asyncio.AbstractEventLoop]:
        bound = self.__dict__.get("_abi_job_host")
        if bound is None:
            raise JobsNotHosted(
                f"The jobs of {type(self).__name__} are not hosted: they run in NATS "
                "mode, from the end of on_initialized until the module stops"
            )
        return bound

    async def atrigger_job(
        self,
        name: str,
        payload: dict[str, Any] | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> JobRun:
        """Trigger one of this module's jobs. Triggers with the same
        ``idempotency_key`` within the stream's duplicate window (2 minutes)
        are one run."""
        host, loop = self._job_host()
        trigger = host.trigger(name, payload, idempotency_key=idempotency_key)
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            return await trigger
        return await asyncio.wrap_future(
            asyncio.run_coroutine_threadsafe(trigger, loop)
        )

    def trigger_job(
        self,
        name: str,
        payload: dict[str, Any] | None = None,
        *,
        idempotency_key: str | None = None,
        timeout: float = 30.0,
    ) -> JobRun:
        """``atrigger_job`` for sync code (an engine request thread); blocks until
        the trigger is stored. On the host's own loop, await ``atrigger_job``."""
        host, loop = self._job_host()
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            raise RuntimeError(
                "trigger_job would block the job host's loop: await atrigger_job"
            )
        return asyncio.run_coroutine_threadsafe(
            host.trigger(name, payload, idempotency_key=idempotency_key), loop
        ).result(timeout)

    def get_workflow(self, name: str) -> Any:
        """One of this module's own workflows, through its bound host: a
        ``WorkflowProxy`` (``start``, ``run``), typed by its declared input and
        output. Its methods are safe to await from any loop; they run on the
        host's. ``JobsNotHosted`` before the host starts and after it stops."""
        from naas_abi_sdk.workflows import host_workflow

        host, loop = self._job_host()
        return host_workflow(host, loop, name, self.workflow_spec(name))


# --- subjects and storage -------------------------------------------------------------


def stream_name(project: str) -> str:
    return f"ABI_JOBS_{project}"


def runs_collection(project: str) -> str:
    return f"job_runs_{_hash(project)[:16]}"


@dataclass(frozen=True)
class JobSubjects:
    project: str
    module_hash: str
    job_hash: str

    @property
    def trigger(self) -> str:
        return f"abi.jobs.{self.project}.trigger.{self.module_hash}.{self.job_hash}"

    def schedule(self, index: int) -> str:
        return f"abi.jobs.{self.project}.schedule.{self.module_hash}.{self.job_hash}.{index}"

    @property
    def cancel(self) -> str:
        return f"abi.jobs.{self.project}.cancel.{self.module_hash}"

    @property
    def done(self) -> str:
        """Core-NATS completion notices of this job's runs. Outside the jobs
        stream's subjects, so that no notice is stored."""
        return f"abi.jobdone.{self.project}.{self.module_hash}.{self.job_hash}"

    @property
    def consumer(self) -> str:
        return f"job-{self.module_hash[:16]}-{self.job_hash[:16]}"


def job_subjects(project: str, module_id: str, job_name: str) -> JobSubjects:
    return JobSubjects(project, _hash(module_id)[:32], _hash(module_id, job_name)[:32])


def run_key(job_name: str, sequence: int) -> str:
    """Run id: one per trigger message (its stream sequence)."""
    return f"{job_name}:{sequence}"


# --- handler context ------------------------------------------------------------------

MAX_LOG_LINES = 200
MAX_LOG_LINE = 2000


@dataclass
class JobContext:
    run_id: str
    job: str
    attempt: int
    trigger: dict[str, str]
    payload: dict[str, Any]
    cancelled: asyncio.Event = field(default_factory=asyncio.Event)
    logs: list[str] = field(default_factory=list)
    skipped: str | None = None

    def log(self, message: str) -> None:
        """Keep a bounded log on the run record."""
        if len(self.logs) < MAX_LOG_LINES:
            self.logs.append(str(message)[:MAX_LOG_LINE])

    def skip(self, reason: str = "") -> None:
        """Record this run as SKIPPED (nothing to do) when the handler returns:
        hidden by default in the System Jobs tab, kept briefly (``JobRetention``)."""
        self.skipped = str(reason)[:MAX_LOG_LINE]


# --- caller side ----------------------------------------------------------------------


class JobRun:
    """A triggered run: read its record, wait for it, or ask its host to cancel it.

    ``duplicate`` is true when the trigger repeated an ``idempotency_key``
    within the stream's duplicate window: JetStream stored nothing, and this
    is the first trigger's run."""

    def __init__(
        self,
        transport: Any,
        project: str,
        module_id: str,
        job_name: str,
        run_id: str,
        documents: Any = None,
        *,
        duplicate: bool = False,
    ):
        self.transport, self.project, self.module_id = transport, project, module_id
        self.job, self.run_id = job_name, run_id
        self.duplicate = duplicate
        self._documents = documents

    def _docs(self) -> Any:
        if self._documents is None:
            from naas_abi_sdk.document import DocumentClient
            from naas_abi_sdk.services.document import DocumentService

            self._documents = DocumentService(
                DocumentClient(self.transport).for_namespace(self.module_id)
            )
        return self._documents

    async def status(self) -> dict[str, Any]:
        """The run record; ``{"status": "QUEUED"}`` until a host has picked it up."""
        from naas_abi_sdk.services.errors import DocumentNotFound

        try:
            return dict(
                (
                    await self._docs().get(runs_collection(self.project), self.run_id)
                ).data
            )
        except DocumentNotFound:
            return {"run_id": self.run_id, "job": self.job, "status": "QUEUED"}

    async def wait(
        self, *, timeout: float | None = None, poll_seconds: float = 0.5
    ) -> dict[str, Any]:
        async def poll() -> dict[str, Any]:
            while True:
                record = await self.status()
                if record.get("status") in TERMINAL_STATUSES:
                    return record
                await asyncio.sleep(poll_seconds)

        return await asyncio.wait_for(poll(), timeout)

    async def cancel(self) -> None:
        """Cooperative: the host running it sets ``ctx.cancelled``."""
        nc = await self.transport.connect()
        await nc.publish(
            job_subjects(self.project, self.module_id, self.job).cancel,
            self.run_id.encode(),
        )


class JobProxy:
    """A job of another module, resolved through discovery (``ModuleProxy.get_job``)."""

    def __init__(
        self,
        transport: Any,
        project: str,
        module_id: str,
        descriptor: JobDescriptor,
        documents: Any = None,
    ):
        self.transport, self.project, self.module_id = transport, project, module_id
        self.descriptor, self._documents = descriptor, documents

    @property
    def name(self) -> str:
        return self.descriptor.name

    async def trigger(
        self,
        payload: dict[str, Any] | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> JobRun:
        """Store a trigger; the run starts when a host takes it. A repeated
        ``idempotency_key`` within the stream's duplicate window (2 minutes) is
        the same run (JetStream message-id dedup), returned with ``duplicate``
        set."""
        from naas_abi_sdk import claim_check  # needs nats; keep jobs.py nats-free

        nc = await self.transport.connect()
        subject = job_subjects(self.project, self.module_id, self.name).trigger
        stream = stream_name(self.project)
        headers = {TRIGGER_HEADER: "manual", "Nats-TTL": "168h"}
        if idempotency_key:
            headers["Nats-Msg-Id"] = _hash(subject, idempotency_key)
        # The run continues this trace (the host reads traceparent off the message).
        with client_span(subject, headers):
            # A payload above the broker limit travels as a claim check.
            body, sent_headers = await claim_check.prepare(
                nc,
                json.dumps(payload or {}).encode(),
                headers,
                reserve=claim_check.stream_header_reserve(stream),
            )
            ack = await nc.jetstream().publish(
                subject, body, headers=sent_headers, stream=stream
            )
        return JobRun(
            self.transport,
            self.project,
            self.module_id,
            self.name,
            run_key(self.name, ack.seq),
            self._documents,
            duplicate=bool(ack.duplicate),
        )
