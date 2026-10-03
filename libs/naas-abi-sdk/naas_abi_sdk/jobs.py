"""Module jobs: scheduled, manual and event-triggered work on JetStream.

Declare jobs like agents and run them in the module's own process::

    class ABIModule(BaseModule):
        jobs = (JobDescriptor("ingest", triggers=(Cron("0 0 6 * * *", time_zone="UTC"),)),)

        async def on_initialized(self):
            self.expose_job("ingest", self.ingest)

        @job(triggers=(Every("1h"),))
        async def summarize(self, ctx: JobContext) -> None: ...

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

from naas_abi_sdk.telemetry import client_span

JOB_CONTRACT_MAJOR = 1
MAX_TRIGGERS = 16
TRIGGER_HEADER = "Abi-Job-Trigger"
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
    "FAILED",
    "TIMED_OUT",
    "CANCELLED",
)
TERMINAL_STATUSES = ("SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELLED")


def _hash(*values: str) -> str:
    return hashlib.sha256(json.dumps(values, ensure_ascii=True).encode()).hexdigest()


# --- triggers -------------------------------------------------------------------------


@dataclass(frozen=True)
class Cron:
    """6-field cron with seconds (``"0 30 9 * * mon-fri"``) or an alias (``"@daily"``)."""

    expression: str
    time_zone: str = ""
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

    @property
    def spec(self) -> str:
        return self.expression.strip()

    def headers(self) -> dict[str, str]:
        headers = {"Nats-Schedule": self.spec}
        if self.time_zone:
            headers["Nats-Schedule-Time-Zone"] = self.time_zone
        return headers


@dataclass(frozen=True, init=False)
class Every:
    """Fixed interval, as a Go duration (``"1h30m"``) or a timedelta; at least 1s."""

    interval: str
    kind = "every"

    def __init__(self, interval: str | timedelta):
        if isinstance(interval, timedelta):
            seconds = interval.total_seconds()
            if seconds < 1 or seconds != int(seconds):
                raise ValueError("Every needs a whole number of seconds, at least 1")
            interval = f"{int(seconds)}s"
        if not isinstance(interval, str) or not _DURATION.fullmatch(interval):
            raise ValueError(f"Not a Go duration: {interval!r}")
        total = sum(
            float(n) * _UNIT_SECONDS[u]
            for n, u in re.findall(r"(\d+(?:\.\d+)?)(ns|us|µs|ms|s|m|h)", interval)
        )
        if total < 1:
            raise ValueError("NATS schedules fire at most once per second")
        object.__setattr__(self, "interval", interval)

    @property
    def spec(self) -> str:
        return self.interval

    @property
    def time_zone(self) -> str:
        return ""

    def headers(self) -> dict[str, str]:
        return {"Nats-Schedule": f"@every {self.interval}"}


@dataclass(frozen=True, init=False)
class OnEvent:
    """Run on events: an ABI event type IRI or any NATS subject (core NATS)."""

    subject: str
    kind = "event"

    def __init__(self, subject: str | None = None, *, event_type: str | None = None):
        if (subject is None) == (event_type is None):
            raise ValueError("OnEvent needs exactly one of subject or event_type")
        if event_type is not None:
            subject = f"evt.{hashlib.sha256(event_type.encode()).hexdigest()[:32]}.>"
        object.__setattr__(self, "subject", subject)

    @property
    def spec(self) -> str:
        return self.subject

    @property
    def time_zone(self) -> str:
        return ""


Trigger = Cron | Every | OnEvent


def _trigger_from_pb(value: pb.JobTrigger) -> Trigger:
    if value.kind == "cron":
        return Cron(value.spec, time_zone=value.time_zone)
    if value.kind == "every":
        return Every(value.spec)
    if value.kind == "event":
        return OnEvent(value.spec)
    raise ValueError(f"Unknown job trigger kind: {value.kind!r}")


# --- descriptors ----------------------------------------------------------------------


@dataclass(frozen=True)
class JobDescriptor:
    name: str
    description: str = ""
    triggers: tuple[Trigger, ...] = ()
    max_concurrency: int = 1
    timeout: timedelta | None = None
    max_attempts: int = 1
    contract_major: int = JOB_CONTRACT_MAJOR

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
        object.__setattr__(self, "triggers", tuple(self.triggers))

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
                pb.JobTrigger(kind=t.kind, spec=t.spec, time_zone=t.time_zone)
                for t in self.triggers
            ],
            max_concurrency=self.max_concurrency,
            max_attempts=self.max_attempts,
            timeout_seconds=self.timeout.total_seconds() if self.timeout else 0.0,
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
        )


JobHandler = Callable[["JobContext"], Awaitable[Any]]


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
            handlers = {
                name: getattr(self, attr_name)
                for name, attr_name in self._decorated_jobs.items()
            }
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

    def missing_job_handlers(self) -> set[str]:
        return {j.name for j in self.jobs} - set(self._job_handlers)


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

    def log(self, message: str) -> None:
        """Keep a bounded log on the run record."""
        if len(self.logs) < MAX_LOG_LINES:
            self.logs.append(str(message)[:MAX_LOG_LINE])


# --- caller side ----------------------------------------------------------------------


class JobRun:
    """A triggered run: read its record, wait for it, or ask its host to cancel it."""

    def __init__(
        self,
        transport: Any,
        project: str,
        module_id: str,
        job_name: str,
        run_id: str,
        documents: Any = None,
    ):
        self.transport, self.project, self.module_id = transport, project, module_id
        self.job, self.run_id = job_name, run_id
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

    async def trigger(self, payload: dict[str, Any] | None = None) -> JobRun:
        from naas_abi_sdk import claim_check  # needs nats; keep jobs.py nats-free

        nc = await self.transport.connect()
        subject = job_subjects(self.project, self.module_id, self.name).trigger
        stream = stream_name(self.project)
        headers = {TRIGGER_HEADER: "manual", "Nats-TTL": "168h"}
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
        )
