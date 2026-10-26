"""Runs a module's jobs: schedules, JetStream consumers, event bridges and run records.

One durable pull consumer per job is shared by every replica, so each trigger
reaches one replica; ``max_ack_pending`` bounds concurrency across replicas.
Delivery is at-least-once: a crash or missed ack redelivers the trigger.
Finished run records are pruned (``JobRetention``); active ones never are.
Attempts are handler starts recorded on the run, not deliveries: a delivery
that cannot read or write its run (the store is down) is retried with backoff
and uses none. A run whose host stopped on its last attempt, or whose trigger
expired (``Nats-TTL``) before its retry, is never run again, so the host's
upkeep fails it (``reap_lost_runs``).

Workflows (``kind="workflow"``) run here as jobs, with a ``FlowContext``; the
host also clears their journals with their run records, and publishes a
core-NATS completion notice when a run is saved terminal (``JobSubjects.done``).
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from naas_abi_sdk.jobs import (
    INPUT_HASH_HEADER,
    MAX_TRIGGER_INPUT_BYTES,
    MAX_TRIGGERS,
    SEAL_HEADER,
    TERMINAL_STATUSES,
    TRIGGER_HEADER,
    TRIGGER_SENDER_HEADERS,
    TRIGGER_TTLS,
    Cron,
    Every,
    JobContext,
    JobDescriptor,
    JobProxy,
    JobRetention,
    JobRun,
    NonRetryable,
    OnEvent,
    go_duration_seconds,
    job_subjects,
    run_key,
    runs_collection,
    seal_fields,
    stream_name,
    trigger_reserve,
)
from naas_abi_sdk.services.errors import DocumentNotFound, VersionConflict
from naas_abi_sdk.services.models import CollectionSpec, FieldSpec
from naas_abi_sdk.telemetry import current_trace_id, record_error, server_span
from naas_abi_sdk.workflows import (
    NOTICE_FALLBACK_POLL_SECONDS,
    FlowContext,
    FlowRuntime,
    StepJournal,
    delete_steps,
    results_collection,
    steps_collection,
)

logger = logging.getLogger(__name__)

MAX_RESULT_BYTES = 64 * 1024

MAX_SCHEDULED_TICK_TTL_SECONDS = 3600
DEFAULT_RETENTION = JobRetention()
# What makes two schedule messages the same schedule (anything else is NATS's own).
SCHEDULE_HEADERS = (
    "Nats-Schedule",
    "Nats-Schedule-Time-Zone",
    "Nats-Schedule-Target",
    "Nats-Schedule-TTL",
    TRIGGER_HEADER,
    SEAL_HEADER,
    # Present only on a schedule with an input (a changed input changes the schedule).
    INPUT_HASH_HEADER,
)
WRONG_LAST_SEQUENCE = 10071  # JetStream: Nats-Expected-Last-Subject-Sequence failed


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stored_at(msg: Any) -> datetime | None:
    """When JetStream stored the trigger (its schedule fired, or someone triggered it)."""
    stamp = getattr(getattr(msg, "metadata", None), "timestamp", None)
    if not isinstance(stamp, datetime):
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)


def _fired_at(msg: Any) -> str:
    return (_stored_at(msg) or datetime.now(timezone.utc)).isoformat()


def _same_trigger(run: dict[str, Any], msg: Any) -> bool:
    """Whether a run record belongs to this trigger message.

    Run ids reuse stream sequences, so a recreated jobs stream hands new triggers
    the ids of old runs. Records from before ``fired_at`` count as a match.
    """
    recorded, stored = run.get("fired_at"), _stored_at(msg)
    return not recorded or stored is None or recorded == stored.isoformat()


def _expires_within(msg: Any, seconds: float) -> bool:
    """Whether the trigger leaves the stream (its ``Nats-TTL``) within ``seconds``."""
    stored = _stored_at(msg)
    ttl = str((msg.headers or {}).get("Nats-TTL", ""))
    if stored is None or not ttl:
        return False
    try:
        lifetime = float(ttl) if ttl.isdigit() else go_duration_seconds(ttl)
    except ValueError:  # "never"
        return False
    deadline = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    return stored + timedelta(seconds=lifetime) <= deadline


# How long a trigger of each kind stays in the stream when its record does not
# say (records written before ``trigger_expires_at``).
_KIND_TTL_SECONDS = {
    "manual": go_duration_seconds(TRIGGER_TTLS["manual"]),
    "event": go_duration_seconds(TRIGGER_TTLS["event"]),
    "schedule": MAX_SCHEDULED_TICK_TTL_SECONDS,
}


def _trigger_expires_at(msg: Any) -> str | None:
    """When the trigger leaves the stream (stored time + ``Nats-TTL``), if known."""
    stored = _stored_at(msg)
    ttl = str((msg.headers or {}).get("Nats-TTL", ""))
    if stored is None or not ttl:
        return None
    try:
        lifetime = float(ttl) if ttl.isdigit() else go_duration_seconds(ttl)
    except ValueError:  # "never"
        return None
    return (stored + timedelta(seconds=lifetime)).isoformat()


def scheduled_tick_ttl(trigger: Cron | Every) -> str:
    """Unprocessed ticks expire: a module back after days runs once, not per missed tick."""
    if isinstance(trigger, Every):
        ttl = max(
            60,
            min(go_duration_seconds(trigger.interval), MAX_SCHEDULED_TICK_TTL_SECONDS),
        )
    else:
        ttl = MAX_SCHEDULED_TICK_TTL_SECONDS
    return f"{int(ttl)}s"


def stream_config(project: str) -> Any:
    """The project's jobs stream: schedules, per-message TTL and direct gets
    (schedules are reconciled by subject). The server allows rollups wherever
    schedules are (whatever ``allow_rollup_hdrs`` says), so one
    ``Nats-Rollup: all`` would purge every module's triggers and schedules:
    behind the broker's auth callout only the engine writes here."""
    from nats.js.api import StreamConfig

    return StreamConfig(
        name=stream_name(project),
        subjects=[f"abi.jobs.{project}.>"],
        allow_msg_schedules=True,
        allow_msg_ttl=True,
        allow_direct=True,
    )


# Flags the stream must have on. Not allow_rollup_hdrs: the server sets it
# with schedules, and asking otherwise would rewrite the stream at every start.
STREAM_FLAGS = {
    "allow_msg_schedules": True,
    "allow_msg_ttl": True,
    "allow_direct": True,
}


async def ensure_stream(js: Any, project: str) -> None:
    """Create the project's jobs stream or set its flags (``stream_config``)."""
    from nats.js.errors import BadRequestError, NotFoundError

    name = stream_name(project)
    try:
        info = await js.stream_info(name)
    except NotFoundError:
        try:
            await js.add_stream(stream_config(project))
            return
        except BadRequestError:
            info = await js.stream_info(name)
    current = info.config
    if any(bool(getattr(current, f, False)) != on for f, on in STREAM_FLAGS.items()):
        for flag, on in STREAM_FLAGS.items():
            setattr(current, flag, on)
        await js.update_stream(current)


# (operation "trigger" | "cancel", job, run id, headers, stored at or None):
# raises RPCError when the caller may not. Scheduled ("cron", "every") and
# "event" triggers are the host's own and are not asked about: the host drops
# any trigger the engine did not seal.
JobAuthorizer = Callable[
    [str, str, str, Mapping[str, str], "datetime | None"], Awaitable[None]
]
# Codes that refuse a trigger for good; anything else is retried later.
REFUSALS = frozenset(
    {
        "PERMISSION_DENIED",
        "UNAUTHENTICATED",
        "NOT_FOUND",
        "JOB_NOT_FOUND",
        "RUN_NOT_FOUND",
        "INVALID_ARGUMENT",
    }
)


def consumer_config(
    project: str,
    module_id: str,
    job: str,
    *,
    max_concurrency: int,
    ack_wait_seconds: float,
) -> Any:
    """The durable pull consumer of a module's job (shared by its replicas)."""
    from nats.js.api import AckPolicy, ConsumerConfig, DeliverPolicy

    subjects = job_subjects(project, module_id, job)
    return ConsumerConfig(
        # A name sends the filter in the API subject
        # ($JS.API.CONSUMER.CREATE.<stream>.<name>.<filter>).
        name=subjects.consumer,
        durable_name=subjects.consumer,
        filter_subject=subjects.trigger,
        ack_policy=AckPolicy.EXPLICIT,
        deliver_policy=DeliverPolicy.NEW,
        ack_wait=ack_wait_seconds,
        # Unlimited: the host counts attempts on the run, so deliveries
        # deferred while the store is down use none. Triggers expire.
        max_deliver=-1,
        max_ack_pending=max_concurrency,
    )


async def ensure_consumer(js: Any, config: Any, project: str, *, update: bool) -> None:
    """Create a job consumer if it is missing, or (``update``) update it."""
    from nats.js.errors import NotFoundError

    stream = stream_name(project)
    if not update:
        try:
            await js.consumer_info(stream, config.durable_name)
            return
        except NotFoundError:
            pass
    await js.add_consumer(stream, config)


# What a host says about each schedule; the target and the kind are the store's.
SCHEDULE_FIELDS = ("Nats-Schedule", "Nats-Schedule-Time-Zone", "Nats-Schedule-TTL")
# Besides those: the trigger's input, the canonical JSON of an object (the body).
SCHEDULE_INPUT = "input"


def schedule_input(value: Any) -> str:
    """A schedule's ``input`` as its canonical JSON (empty: none), or ValueError:
    a JSON object of at most ``MAX_TRIGGER_INPUT_BYTES``."""
    if value in (None, ""):
        return ""
    if not isinstance(value, str) or len(value.encode()) > MAX_TRIGGER_INPUT_BYTES:
        raise ValueError(
            f"an input is the JSON text of an object of {MAX_TRIGGER_INPUT_BYTES} "
            "bytes at most"
        )
    try:
        parsed = json.loads(value)
    except ValueError:
        raise ValueError("an input is JSON") from None
    if not isinstance(parsed, dict):
        raise ValueError("an input is a JSON object")
    # As ``Cron.input_json`` writes it: the same input is the same bytes.
    return (
        json.dumps(parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        if parsed
        else ""
    )


async def set_schedules(
    js: Any,
    project: str,
    module_id: str,
    job: str,
    schedules: list[dict[str, str]],
    *,
    seal: Callable[[bytes], str] | None = None,
) -> None:
    """A job's schedules, one message each, aimed at its own trigger; the
    indexes beyond them purged. A schedule's ``input`` is its body, each fired
    trigger's payload (``{}`` without one). ``seal``: the engine's, over that
    body, copied by the server onto every trigger a schedule fires."""
    subjects = job_subjects(project, module_id, job)
    for index, fields in enumerate(schedules):
        headers = {k: v for k, v in fields.items() if k in SCHEDULE_FIELDS}
        given = schedule_input(fields.get(SCHEDULE_INPUT))
        body = given.encode() if given else b"{}"
        if given:
            # A changed input is a changed schedule (published again).
            headers[INPUT_HASH_HEADER] = hashlib.sha256(given.encode()).hexdigest()[:32]
        if seal is not None:
            headers[SEAL_HEADER] = seal(body)
        headers["Nats-Schedule-Target"] = subjects.trigger
        headers[TRIGGER_HEADER] = "schedule"
        await ensure_schedule(js, project, subjects.schedule(index), headers, body)
    await remove_schedules(js, subjects, len(schedules))


async def ensure_schedule(
    js: Any, project: str, subject: str, headers: dict[str, str], body: bytes = b"{}"
) -> None:
    """Publish a schedule only when it is missing or changed.

    Replacing a schedule message restarts an ``@every`` interval: hosts that
    restart more often than the interval would keep it from ever firing. The
    publish expects the sequence just read, so hosts starting together write
    it once; the loser reads it again. ``body`` is the trigger's input
    (``b"{}"`` without one), delivered as each run's payload; the input's hash
    is in the headers, so a changed input publishes the schedule again.
    """
    from nats.js.errors import BadRequestError, NotFoundError

    stream = stream_name(project)
    wanted = {name: headers.get(name) for name in SCHEDULE_HEADERS}
    for _ in range(3):
        try:
            current = await js.get_last_msg(stream, subject, direct=True)
        except NotFoundError:
            sequence = 0
        else:
            found = current.headers or {}
            if {name: found.get(name) for name in SCHEDULE_HEADERS} == wanted:
                return
            sequence = current.seq
        try:
            await js.publish(
                subject,
                body,
                headers={
                    **headers,
                    "Nats-Expected-Last-Subject-Sequence": str(sequence),
                },
                stream=stream,
            )
            return
        except BadRequestError as error:
            if error.err_code != WRONG_LAST_SEQUENCE:
                raise
    logger.warning(
        "Schedule %s kept changing while it was reconciled; "
        "keeping the one another host wrote",
        subject,
    )


async def remove_schedules(js: Any, subjects: Any, keep: int) -> None:
    """Purge a job's schedules from index ``keep`` on."""
    for index in range(keep, MAX_TRIGGERS):
        await js.purge_stream(
            stream_name(subjects.project), subject=subjects.schedule(index)
        )


class EngineUnavailable(RuntimeError):
    """The engine that seals triggers did not answer: try again later."""


class JobHost:
    def __init__(
        self,
        transport: Any,
        documents: Any,
        module_id: str,
        project: str,
        handlers: dict[str, tuple[JobDescriptor, Any]],
        *,
        instance_id: str = "",
        heartbeat_seconds: float = 10.0,
        ack_wait_seconds: float = 30.0,
        fetch_timeout_seconds: float = 1.0,
        backoff_base_seconds: float = 5.0,
        max_backoff_seconds: float = 300.0,
        close_grace_seconds: float = 10.0,
        close_cancel_seconds: float = 15.0,
        retention: JobRetention | None = DEFAULT_RETENTION,
        lost_after_seconds: float = 300.0,
        completion_error_after_seconds: float = 60.0,
        authorize: JobAuthorizer | None = None,
        control: Any = None,
        module_documents: Any = None,
        workflow_poll_seconds: float = NOTICE_FALLBACK_POLL_SECONDS,
    ):
        """``authorize``: asks whether the caller named by a manual trigger or a
        cancel may trigger the job or cancel the run (discovery:TriggerJob,
        CancelJobRun). Every host the SDK and the engine start has one; without
        it (tests of the host alone) nothing is authorized.

        ``control``: a ``BrokerControl`` creating the jobs stream and the
        consumers, writing the schedules and checking seals (a module behind the
        broker's auth callout may do none of it); None does it over
        ``transport``."""
        self.authorize = authorize
        self.transport, self.documents = transport, documents
        self.module_id, self.project = module_id, project
        self.handlers, self.instance_id = handlers, instance_id
        self.heartbeat_seconds, self.ack_wait_seconds = (
            heartbeat_seconds,
            ack_wait_seconds,
        )
        self.fetch_timeout_seconds = fetch_timeout_seconds
        self.backoff_base_seconds, self.max_backoff_seconds = (
            backoff_base_seconds,
            max_backoff_seconds,
        )
        self.close_grace_seconds = close_grace_seconds
        self.close_cancel_seconds = close_cancel_seconds
        self.retention = retention
        self.lost_after_seconds = lost_after_seconds
        # A completion still unsaved after this long is logged as an error.
        self.completion_error_after_seconds = completion_error_after_seconds
        self.control = control
        self.collection = runs_collection(project)
        # What workflow runs need: their journal's store, and how to read the runs
        # of other modules (``module_documents(module_id)``; None: over the transport).
        self.workflow_poll_seconds = workflow_poll_seconds
        self._flow_runtime = FlowRuntime(
            transport,
            documents,
            module_id,
            project,
            module_documents,
            workflow_poll_seconds,
        )
        self._running: dict[str, JobContext] = {}
        self._work: dict[str, asyncio.Task] = {}
        # Runs stopped by close(): retried elsewhere, never recorded as user cancels.
        self._interrupted: set[str] = set()
        self._tasks: set[asyncio.Task] = set()
        self._loops: list[asyncio.Task] = []
        self._consumers: list[asyncio.Task] = []
        self._subscriptions: list[Any] = []
        self._closing = False
        self._draining = False

    def _subjects(self, descriptor: JobDescriptor):
        return job_subjects(self.project, self.module_id, descriptor.name)

    def _consumer_config(self, descriptor: JobDescriptor) -> Any:
        return consumer_config(
            self.project,
            self.module_id,
            descriptor.name,
            max_concurrency=descriptor.max_concurrency,
            ack_wait_seconds=self.ack_wait_seconds,
        )

    @property
    def _claims(self) -> Any:
        """Claim checks through the engine, when this host has broker control."""
        from naas_abi_sdk import claim_check

        return None if self.control is None else claim_check.ThroughEngine(self.control)

    async def _ensure_consumer(
        self, js: Any, descriptor: JobDescriptor, *, update: bool
    ) -> None:
        """The jobs stream and this job's consumer: through the engine when
        it answers, else over this host's own connection."""
        if self.control is not None and await self.control.request(
            "ensure_job",
            project=self.project,
            job=descriptor.name,
            max_concurrency=descriptor.max_concurrency,
            ack_wait_seconds=self.ack_wait_seconds,
            update=update,
        ):
            return
        await ensure_stream(js, self.project)
        await ensure_consumer(
            js, self._consumer_config(descriptor), self.project, update=update
        )

    # --- lifecycle -----------------------------------------------------------------------

    async def prepare(self) -> None:
        """Create each job's consumer if it is missing, and nothing else.

        A consumer delivers only triggers stored after it was created
        (``DeliverPolicy.NEW``). A rollout's process calls this before its
        instance can serve, so a trigger for a job only it declares, sent after
        the cutover but before ``start``, waits for it instead of being skipped.
        It never changes an existing consumer, publishes schedules, bridges
        events or fetches: those stay with the serving generation until
        ``start``.
        """

        js = (await self.transport.connect()).jetstream()
        for descriptor, _ in self.handlers.values():
            await self._ensure_consumer(js, descriptor, update=False)

    async def start(self) -> None:
        await self.documents.ensure_collection(
            CollectionSpec(
                name=self.collection,
                # Retention and the System Jobs tab query runs by these.
                fields=tuple(
                    FieldSpec(name=f, type="string", indexed=True)
                    for f in ("job", "status", "finished_at")
                ),
            )
        )
        if any(d.kind == "workflow" for d, _ in self.handlers.values()):
            await StepJournal(self.documents, self.project, "").ensure()
        nc = await self.transport.connect()
        js = nc.jetstream()
        cancel_subject = None
        for descriptor, handler in self.handlers.values():
            subjects = self._subjects(descriptor)
            cancel_subject = subjects.cancel
            # Created, or updated in place to this code's limits.
            await self._ensure_consumer(js, descriptor, update=True)
            await self.reconcile_schedules(js, descriptor)
            for event in descriptor.events:
                self._subscriptions.append(
                    await nc.subscribe(
                        event.subject,
                        queue=f"{subjects.consumer}-events",
                        cb=self._event_bridge(js, descriptor, event),
                    )
                )
            sub = await js.pull_subscribe_bind(
                durable=subjects.consumer, stream=stream_name(self.project)
            )
            self._consumers.append(
                asyncio.create_task(self._consume(sub, descriptor, handler))
            )
        if cancel_subject:
            self._subscriptions.append(
                await nc.subscribe(cancel_subject, cb=self._on_cancel)
            )
        if self.handlers:
            self._loops.append(asyncio.create_task(self._upkeep()))

    async def drain(self, timeout: float) -> None:
        """Stop pulling new jobs. Runs already started continue until timeout."""
        self._draining = True
        for loop in self._consumers:
            loop.cancel()
        await asyncio.gather(*self._consumers, return_exceptions=True)
        self._consumers.clear()
        for subscription in self._subscriptions:
            with contextlib.suppress(Exception):
                await subscription.unsubscribe()
        self._subscriptions.clear()
        if self._tasks:
            await asyncio.wait(set(self._tasks), timeout=timeout)

    async def close(self) -> None:
        self._closing = True
        self._draining = True
        loops = [*self._consumers, *self._loops]
        for loop in loops:
            loop.cancel()
        await asyncio.gather(*loops, return_exceptions=True)
        self._consumers.clear()
        self._loops.clear()
        for subscription in self._subscriptions:
            with contextlib.suppress(Exception):
                await subscription.unsubscribe()
        # The first half of the grace lets runs end on their own and keep
        # their outcome: a short run a deploy happens to catch is no failure.
        # The rest are asked to stop, and retried elsewhere if they may be.
        finish = self.close_grace_seconds / 2
        if self._work:
            await asyncio.wait(set(self._work.values()), timeout=finish)
        for run_id, context in list(self._running.items()):
            work = self._work.get(run_id)
            if work is not None and work.done():
                continue
            self._interrupted.add(run_id)
            context.cancelled.set()
        if not self._tasks:
            return
        _, pending = await asyncio.wait(
            set(self._tasks), timeout=self.close_grace_seconds - finish
        )
        if pending:
            # Ignored the cancel request: cancel the handlers themselves, so each run
            # is still recorded and nak'ed before the connection goes away.
            for work in list(self._work.values()):
                work.cancel()
            await asyncio.wait(pending, timeout=self.close_cancel_seconds)

    def _spawn(self, coroutine: Any) -> asyncio.Task:
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._observe)
        return task

    def _observe(self, task: asyncio.Task) -> None:
        self._tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            logger.error("Job host task failed", exc_info=task.exception())

    async def _consume(self, sub: Any, descriptor: JobDescriptor, handler: Any) -> None:
        from nats.errors import TimeoutError as NATSTimeoutError

        slots = asyncio.Semaphore(descriptor.max_concurrency)
        while not self._closing and not self._draining:
            await slots.acquire()
            try:
                messages = await sub.fetch(1, timeout=self.fetch_timeout_seconds)
            except (NATSTimeoutError, asyncio.TimeoutError):
                slots.release()
                continue
            except Exception:  # broker hiccup: retry, never kill the loop
                slots.release()
                if self._closing:
                    return
                logger.warning(
                    "Job fetch failed for %s; retrying", descriptor.name, exc_info=True
                )
                await asyncio.sleep(1)
                continue
            for message in messages:
                self._spawn(
                    self._handle_and_release(descriptor, handler, message, slots)
                )
            if not messages:
                slots.release()

    async def _handle_and_release(self, descriptor, handler, message, slots) -> None:
        try:
            await self.handle(descriptor, handler, message)
        finally:
            slots.release()

    # --- schedules and events --------------------------------------------------------------

    async def reconcile_schedules(self, js: Any, descriptor: JobDescriptor) -> None:
        """One schedule message per Cron/Every trigger; stale indexes are purged.
        Through the engine when it answers: a module behind the broker's auth
        callout writes nothing into the jobs stream. A trigger's input travels
        as ``input`` (its canonical JSON), the schedule's body."""
        schedules = [
            {
                **{
                    k: v for k, v in trigger.headers().items() if k != INPUT_HASH_HEADER
                },
                "Nats-Schedule-TTL": scheduled_tick_ttl(trigger),
                **({"input": trigger.input_json} if trigger.input else {}),
            }
            for trigger in descriptor.schedules
        ]
        if self.control is not None and await self.control.request(
            "set_schedules",
            project=self.project,
            job=descriptor.name,
            schedules=schedules,
        ):
            return
        await set_schedules(
            js, self.project, self.module_id, descriptor.name, schedules
        )

    async def bridge_event(
        self,
        js: Any,
        descriptor: JobDescriptor,
        msg: Any,
        trigger: OnEvent | None = None,
    ) -> None:
        """Republish a core-NATS event as a durable trigger (deduplicated per event),
        unless the trigger's filter rejects it.

        Either side may be above the broker limit: the event is read back from
        its claim check, and the trigger (wrapped, so larger) is sent as one.
        """
        from naas_abi_sdk import claim_check

        nc = await self.transport.connect()
        raw = await claim_check.resolve(nc, msg, store=self._claims)
        try:
            data: Any = json.loads(raw) if raw else None
        except (ValueError, UnicodeDecodeError):
            data = raw.decode(errors="replace")
        if trigger is not None and not trigger.matches(data):
            return
        stream = stream_name(self.project)
        headers = {TRIGGER_HEADER: "event", "Nats-TTL": TRIGGER_TTLS["event"]}
        event_id = (getattr(msg, "headers", None) or {}).get("Nats-Msg-Id")
        if event_id:
            identity = json.dumps(
                [self._subjects(descriptor).trigger, msg.subject, event_id]
            )
            headers["Nats-Msg-Id"] = hashlib.sha256(identity.encode()).hexdigest()
        subjects = self._subjects(descriptor)
        payload = json.dumps({"subject": msg.subject, "data": data}).encode()
        body, sent = await claim_check.prepare(
            nc,
            payload,
            headers,
            scope=claim_check.job_scope(self.project, subjects.module_hash),
            reserve=trigger_reserve(len(payload)),
            store=self._claims,
        )
        if self.control is not None:
            # Through the engine (a module writes nothing into the jobs stream);
            # it stores an event trigger for the job's own module only.
            import base64

            answer = await self.control.request(
                "trigger",
                project=self.project,
                module_id=self.module_id,
                job=descriptor.name,
                body=base64.b64encode(body).decode(),
                headers={
                    k: v for k, v in (sent or {}).items() if k in TRIGGER_SENDER_HEADERS
                },
                kind="event",
            )
            if answer is not None:
                return
        await js.publish(subjects.trigger, body, headers=sent, stream=stream)

    # --- cancellation ------------------------------------------------------------------------

    def cancel(self, run_id: str) -> bool:
        context = self._running.get(run_id)
        if context is None:
            return False
        context.cancelled.set()
        return True

    def _event_bridge(
        self, js: Any, descriptor: JobDescriptor, trigger: OnEvent
    ) -> Any:
        async def on_event(msg: Any) -> None:
            if self._draining or self._closing:
                return
            self._spawn(self.bridge_event(js, descriptor, msg, trigger))

        return on_event

    # --- the module's own triggers -----------------------------------------------------

    async def trigger(
        self,
        name: str,
        payload: dict[str, Any] | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> JobRun:
        """Trigger one of this host's jobs (``JobsMixin.trigger_job``)."""
        if name not in self.handlers:
            raise ValueError(f"Module {self.module_id} has no job named {name!r}")
        descriptor = self.handlers[name][0]
        # The module's own trigger: as the module (or the engine), for no user.
        return await JobProxy(
            self.transport, self.project, self.module_id, descriptor, self.documents
        ).trigger(payload, idempotency_key=idempotency_key, on_behalf_of=False)

    # --- upkeep: lost runs and retention ---------------------------------------------------

    async def _upkeep(self) -> None:
        interval = (self.retention or DEFAULT_RETENTION).interval.total_seconds()
        while not self._closing:
            for upkeep in (self.reap_lost_runs, self.prune):
                try:
                    await upkeep()
                except Exception:  # a store hiccup must not stop the next pass
                    logger.warning("Job run upkeep failed; retrying", exc_info=True)
            await asyncio.sleep(interval)

    async def reap_lost_runs(self, now: datetime | None = None) -> int:
        """Fail the runs nothing will finish; returns how many.

        - A RUNNING run on its last attempt whose heartbeats stopped more than
          ``lost_after_seconds`` ago: its host stopped and no attempt is left.
        - A RUNNING run with attempts left and heartbeats stopped as long, or a
          RETRYING run past its retry time, whose trigger left the stream (its
          ``Nats-TTL`` passed): nothing can redeliver it.

        Other runs with attempts left are JetStream's: their redelivery updates
        the record. Runs on this host are never touched.
        """
        now = now or datetime.now(timezone.utc)
        cutoff = (now - timedelta(seconds=self.lost_after_seconds)).isoformat()
        reaped = 0
        for name, (descriptor, _) in self.handlers.items():
            page = await self.documents.find(
                self.collection,
                where=[("job", "eq", name), ("status", "in", ["RUNNING", "RETRYING"])],
                limit=1000,
            )
            for doc in page.items:
                if doc.id in self._running:
                    continue
                error = await self._lost(descriptor, doc.id, doc.data, now, cutoff)
                if error is None:
                    continue
                try:
                    await self.documents.put(
                        self.collection,
                        doc.id,
                        {
                            **doc.data,
                            "status": "FAILED",
                            "error": error,
                            "finished_at": now.isoformat(),
                        },
                        if_version=doc.version,
                    )
                    reaped += 1
                    await self._notify(descriptor, doc.id, "FAILED")
                except (DocumentNotFound, VersionConflict):
                    continue  # its host is alive after all, or another replica reaped it
        return reaped

    async def _lost(
        self,
        descriptor: JobDescriptor,
        run_id: str,
        run: dict[str, Any],
        now: datetime,
        cutoff: str,
    ) -> str | None:
        """Why nothing will finish this run, or None while something still can."""
        last_seen = run.get("heartbeat_at") or run.get("started_at") or ""
        if run.get("status") == "RETRYING":
            due = run.get("retry_at") or last_seen
            if not due or due > now.isoformat():
                return None
            error = "Trigger expired before it could be retried"
        else:
            if not last_seen or last_seen >= cutoff:
                return None
            lost = f"Lost: no heartbeat since {last_seen}"
            if run.get("attempt", 1) >= run.get("max_attempts", 1):
                return f"{lost} (its host stopped before the run finished)"
            error = f"{lost}, and its trigger expired before it could be retried"
        return error if await self._trigger_gone(descriptor, run_id, run, now) else None

    async def _trigger_gone(
        self,
        descriptor: JobDescriptor,
        run_id: str,
        run: dict[str, Any],
        now: datetime | None = None,
    ) -> bool:
        """Whether the run's trigger message left the jobs stream: its
        ``Nats-TTL`` passed. Read from the run, never from the stream (a host
        may not read other modules' triggers there): ``trigger_expires_at``,
        else ``fired_at`` plus the longest TTL of the trigger's kind."""
        now = now or datetime.now(timezone.utc)
        try:
            if run.get("trigger_expires_at"):
                expires = datetime.fromisoformat(run["trigger_expires_at"])
            elif run.get("fired_at"):
                kind = (run.get("trigger") or {}).get("kind", "manual")
                lifetime = _KIND_TTL_SECONDS.get(kind, _KIND_TTL_SECONDS["manual"])
                expires = datetime.fromisoformat(run["fired_at"]) + timedelta(
                    seconds=lifetime
                )
            else:
                return False
        except (TypeError, ValueError):
            return False
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return now >= expires

    async def prune(self, now: datetime | None = None) -> int:
        """One retention pass over this host's jobs; returns the runs deleted.

        Finished runs older than ``max_age`` go (skipped ones after
        ``skipped_max_age``), then each job keeps its newest
        ``max_runs_per_job``. At most ``batch`` deletions per pass.
        """
        if self.retention is None:
            return 0
        retention = self.retention
        now = now or datetime.now(timezone.utc)
        budget = retention.batch
        kept = [s for s in TERMINAL_STATUSES if s != "SKIPPED"]
        for name in self.handlers:
            workflow = self.handlers[name][0].kind == "workflow"
            for statuses, max_age in (
                (kept, retention.max_age),
                (["SKIPPED"], retention.skipped_max_age),
            ):
                if budget <= 0:
                    return retention.batch
                cutoff = (now - max_age).isoformat()
                budget -= await self._delete(
                    [
                        ("job", "eq", name),
                        ("status", "in", statuses),
                        ("finished_at", "lt", cutoff),
                    ],
                    budget,
                    workflow=workflow,
                )
            if budget <= 0:
                return retention.batch
            finished = [("job", "eq", name), ("status", "in", list(TERMINAL_STATUSES))]
            excess = await self.documents.count(self.collection, finished) - (
                retention.max_runs_per_job
            )
            if excess > 0:
                budget -= await self._delete(
                    finished,
                    min(excess, budget),
                    order_by=("finished_at", "asc"),
                    workflow=workflow,
                )
        return retention.batch - budget

    async def _delete(
        self, where: list, limit: int, order_by: Any = None, workflow: bool = False
    ) -> int:
        page = await self.documents.find(
            self.collection, where=where, order_by=order_by, limit=min(limit, 1000)
        )
        deleted = 0
        for doc in page.items[:limit]:
            if workflow:
                # Before the record: a failure here leaves the run for the next
                # pass, which still finds it; after, its journal would stay forever.
                await delete_steps(
                    self.documents,
                    steps_collection(self.project),
                    results_collection(self.project),
                    doc.id,
                )
            try:
                await self.documents.delete(
                    self.collection, doc.id, if_version=doc.version
                )
                deleted += 1
            except (DocumentNotFound, VersionConflict):
                continue  # another replica pruned or updated it
        return deleted

    async def _notify(
        self, descriptor: JobDescriptor, run_id: str, status: str
    ) -> None:
        """Tell waiters a run ended (core NATS, at-most-once: they poll too). Sent
        after the record is saved; never fails the run."""
        try:
            nc = await self.transport.connect()
            # run id and status: a few hundred bytes at most
            await nc.publish(
                self._subjects(descriptor).done,
                json.dumps({"run_id": run_id, "status": status}).encode(),
            )
        except Exception:
            logger.warning(
                "Could not publish the completion of run %s", run_id, exc_info=True
            )

    async def _on_cancel(self, msg: Any) -> None:
        run_id = msg.data.decode(errors="replace")
        job = run_id.rpartition(":")[0]
        if run_id not in self._running or job not in self.handlers:
            return
        try:
            sealed = await self._sealed(
                getattr(msg, "subject", ""), "cancel", msg.data, msg.headers
            )
        except Exception:  # noqa: BLE001 - a cancel is best effort
            logger.warning("Could not check a cancel's seal; ignored", exc_info=True)
            return
        if not sealed:
            logger.warning(
                "Dropped a cancel on %s the engine did not seal", msg.subject
            )
            return
        if self.authorize is not None:
            try:
                await self.authorize("cancel", job, run_id, msg.headers or {}, None)
            except Exception as exc:  # noqa: BLE001 - a refused cancel changes nothing
                logger.warning("Job cancel of %s refused: %s", run_id, exc)
                return
        self.cancel(run_id)

    async def _sealed(
        self, subject: str, kind: str, body: bytes, headers: dict[str, str] | None
    ) -> bool:
        """Whether the engine wrote this trigger or cancel (its seal).

        Behind the broker's auth callout (a transport logged in with a service
        key) nothing is taken on faith: with no engine answering, this raises
        and the message is redelivered, so an engine restart never lets a
        forged or unsealed message run. Only a host without a callout (no
        broker control, or a broker where nothing is sealed) takes a message as
        it is."""
        if self.control is None:
            return True
        confined = getattr(self.transport, "credentials", None) is not None
        seal = (headers or {}).get(SEAL_HEADER, "")
        if not seal:
            # Nothing unsealed is written behind the callout: unless no engine
            # answers at all, this one was forged.
            answer = await self.control.request("verify_trigger", fields=[], seal="-")
            if answer is None and confined:
                raise EngineUnavailable("no engine answered to check a seal")
            return answer is None
        answer = await self.control.request(
            "verify_trigger",
            fields=seal_fields(subject, kind, body, headers),
            seal=seal,
        )
        if answer is None and confined:
            raise EngineUnavailable("no engine answered to check a seal")
        return answer is None or bool(answer.get("valid"))

    # --- running one trigger ---------------------------------------------------------------

    def _backoff(self, attempt: int) -> float:
        return min(
            self.backoff_base_seconds * 2 ** (attempt - 1), self.max_backoff_seconds
        )

    async def _save(
        self,
        run_id: str,
        fields: dict[str, Any],
        *,
        only_running: bool = False,
        replace: bool = False,
    ) -> None:
        """Merge ``fields`` into the run (CAS); ``replace`` drops what was there."""
        for _ in range(3):
            try:
                existing = await self.documents.get(self.collection, run_id)
            except DocumentNotFound:
                if only_running:
                    return
                try:
                    await self.documents.put(
                        self.collection,
                        run_id,
                        {"created_at": _now(), **fields},
                        if_version=0,
                    )
                    return
                except VersionConflict:
                    continue
            if only_running and existing.data.get("status") != "RUNNING":
                return
            data = {"created_at": _now()} if replace else existing.data
            try:
                await self.documents.put(
                    self.collection,
                    run_id,
                    {**data, **fields},
                    if_version=existing.version,
                )
                return
            except VersionConflict:
                continue
        raise VersionConflict("VERSION_CONFLICT", f"Could not save job run {run_id}")

    async def _heartbeat(self, msg: Any) -> None:
        while True:
            await asyncio.sleep(self.heartbeat_seconds)
            await msg.in_progress()

    async def _persist_progress(self, context: JobContext) -> None:
        while True:
            await asyncio.sleep(self.heartbeat_seconds)
            try:
                await self._save(
                    context.run_id,
                    {"logs": list(context.logs), "heartbeat_at": _now()},
                    only_running=True,
                )
            except Exception:
                logger.warning(
                    "Job progress persistence failed; retrying", exc_info=True
                )

    async def _save_completion(
        self, run_id: str, fields: dict[str, Any], heartbeat: asyncio.Task
    ) -> None:
        """Save a finished run, retrying until the store takes it.

        The run keeps its delivery (and its concurrency slot) meanwhile: acking
        before the result is saved could lose it, nak'ing would run it again.
        Past ``completion_error_after_seconds`` each retry logs an error.
        """
        loop = asyncio.get_running_loop()
        failing_since: float | None = None
        while True:
            if heartbeat.done():
                await heartbeat
            try:
                await self._save(run_id, fields)
                return
            except Exception:
                if failing_since is None:
                    failing_since = loop.time()
                outage = loop.time() - failing_since
                logger.log(
                    logging.ERROR
                    if outage >= self.completion_error_after_seconds
                    else logging.WARNING,
                    "Job run %s could not save its completion for %.0fs; retrying "
                    "(it keeps its concurrency slot until the store recovers)",
                    run_id,
                    outage,
                    exc_info=True,
                )
                if self._closing or heartbeat.done():
                    raise
                # Keep renewing delivery while retaining the completed result in memory.
                await asyncio.sleep(min(self.heartbeat_seconds, 1.0))

    @staticmethod
    async def _retire(msg: Any, status: str) -> None:
        if status in ("SUCCEEDED", "SKIPPED", "CANCELLED"):
            await msg.ack()
        else:
            await msg.term()

    @staticmethod
    def _result(value: Any) -> Any:
        try:
            encoded = json.dumps(value)
        except (TypeError, ValueError):
            encoded = json.dumps(str(value))
        if len(encoded.encode()) > MAX_RESULT_BYTES:
            return {"truncated": True, "preview": encoded[:2000]}
        return json.loads(encoded)

    async def handle(self, descriptor: JobDescriptor, handler: Any, msg: Any) -> None:
        """Run one delivery inside a CONSUMER span continuing its trigger's trace."""
        attributes = {
            "abi.module.id": self.module_id,
            "abi.job.name": descriptor.name,
            "abi.job.run_id": run_key(descriptor.name, msg.metadata.sequence.stream),
            "abi.job.delivery": msg.metadata.num_delivered,
        }
        with server_span(
            getattr(msg, "subject", ""),
            msg.headers,
            kind="consumer",
            name=f"job {descriptor.name}",
            attributes=attributes,
        ):
            status = await self._handle_delivery(descriptor, handler, msg)
            if status not in ("SUCCEEDED", "SKIPPED", "CANCELLED"):
                record_error(status)

    async def _payload(self, msg: Any) -> dict[str, Any]:
        """The trigger's payload, read back from its claim check when large."""
        from naas_abi_sdk import claim_check

        data = msg.data
        if claim_check.carries_reference(msg):
            data = await claim_check.resolve(
                await self.transport.connect(), msg, store=self._claims
            )
        try:
            payload = json.loads(data) if data else {}
        except (ValueError, UnicodeDecodeError):
            payload = {"raw": data.decode(errors="replace")}
        return payload if isinstance(payload, dict) else {"value": payload}

    async def _defer(
        self, msg: Any, run_id: str, delivery: int, error: Exception
    ) -> str:
        """The run could not be read or recorded: redeliver later, using no attempt."""
        delay = self._backoff(delivery)
        logger.error(
            "Job run %s could not start (delivery %d): %s; redelivering in %gs",
            run_id,
            delivery,
            error,
            delay,
            exc_info=error,
        )
        await msg.nak(delay=delay)
        return "DEFERRED"

    async def _refuse(
        self,
        msg: Any,
        run_id: str,
        descriptor: JobDescriptor,
        trigger: dict[str, str],
        error: Exception,
    ) -> str:
        """A trigger whose caller may not trigger the job: recorded as failed,
        never run, never redelivered."""
        logger.warning("Job trigger %s refused: %s", run_id, error)
        try:
            await self._save(
                run_id,
                {
                    "job": descriptor.name,
                    "run_id": run_id,
                    "module_id": self.module_id,
                    "status": "FAILED",
                    "attempt": 0,
                    "max_attempts": descriptor.max_attempts,
                    "trigger": trigger,
                    "instance": self.instance_id,
                    "sequence": msg.metadata.sequence.stream,
                    "fired_at": _fired_at(msg),
                    "finished_at": _now(),
                    "error": f"Trigger refused: {getattr(error, 'code', '') or error}",
                },
                replace=True,
            )
        except Exception as exc:  # noqa: BLE001 - logged and redelivered by _defer
            return await self._defer(msg, run_id, msg.metadata.num_delivered, exc)
        await msg.term()
        return "FAILED"

    async def _handle_delivery(
        self, descriptor: JobDescriptor, handler: Any, msg: Any
    ) -> str:
        sequence, delivery = msg.metadata.sequence.stream, msg.metadata.num_delivered
        run_id = run_key(descriptor.name, sequence)
        scheduler = (msg.headers or {}).get("Nats-Scheduler")
        own = self._subjects(descriptor).schedule(0).rpartition(".")[0] + "."
        if scheduler and not scheduler.startswith(own):
            # The server names the schedule that fired (a client cannot set
            # it), and any module may target its own schedules at this subject.
            logger.warning(
                "Job %s: dropped a trigger fired by another module's schedule %s",
                descriptor.name,
                scheduler,
            )
            await msg.term()
            return "REFUSED"
        headers = msg.headers or {}
        try:
            sealed = await self._sealed(
                getattr(msg, "subject", ""),
                headers.get(TRIGGER_HEADER, "manual"),
                msg.data,
                headers,
            )
        except Exception as exc:  # noqa: BLE001 - the engine is away: later
            return await self._defer(msg, run_id, delivery, exc)
        if not sealed:
            # Behind the broker's auth callout only the engine writes triggers;
            # anything else landed here by a JetStream answer a module aimed.
            logger.warning(
                "Job %s: dropped a trigger the engine did not seal", descriptor.name
            )
            await msg.term()
            return "REFUSED"
        try:
            existing = await self.documents.get(self.collection, run_id)
        except DocumentNotFound:
            existing = None
        except Exception as exc:  # noqa: BLE001 - logged and redelivered by _defer
            return await self._defer(msg, run_id, delivery, exc)
        # A recreated stream reuses sequences: an older trigger's run is replaced.
        replace = existing is not None and not _same_trigger(existing.data, msg)
        if existing is not None and not replace:
            if existing.data.get("status") in TERMINAL_STATUSES:
                status = existing.data["status"]
                await self._retire(msg, status)
                return status
            # Attempts are handler starts recorded on the run, not deliveries.
            attempt = int(existing.data.get("attempt") or 0) + 1
            if attempt > descriptor.max_attempts:
                # Its last attempt never finished: the upkeep fails the run once
                # its heartbeats stop (reap_lost_runs).
                logger.warning(
                    "Job run %s used its %d attempts; dropping delivery %d",
                    run_id,
                    descriptor.max_attempts,
                    delivery,
                )
                await msg.term()
                return str(existing.data.get("status"))
        else:
            attempt = 1
        headers = msg.headers or {}
        trigger = {"kind": headers.get(TRIGGER_HEADER, "manual")}
        if headers.get("Nats-Scheduler"):
            trigger["scheduler"] = headers["Nats-Scheduler"]
        elif trigger["kind"] == "schedule":
            trigger["kind"] = "manual"  # only the server fires a schedule
        if attempt == 1 and trigger["kind"] == "manual" and self.authorize is not None:
            try:
                await self.authorize(
                    "trigger", descriptor.name, run_id, headers, _stored_at(msg)
                )
            except Exception as exc:  # noqa: BLE001 - refused, or retried below
                if getattr(exc, "code", "") not in REFUSALS:
                    return await self._defer(msg, run_id, delivery, exc)
                return await self._refuse(msg, run_id, descriptor, trigger, exc)
        fired_at = _fired_at(msg)
        try:
            payload = await self._payload(msg)
            await self._save(
                run_id,
                {
                    "job": descriptor.name,
                    "run_id": run_id,
                    "module_id": self.module_id,
                    "status": "RUNNING",
                    "attempt": attempt,
                    "max_attempts": descriptor.max_attempts,
                    "trigger": trigger,
                    "payload": payload,
                    "instance": self.instance_id,
                    "sequence": sequence,
                    "fired_at": fired_at,
                    "trigger_expires_at": _trigger_expires_at(msg),
                    "started_at": _now(),
                    "heartbeat_at": _now(),
                    "trace_id": current_trace_id(),
                    "error": "",
                },
                replace=replace,
            )
        except Exception as exc:  # noqa: BLE001 - logged and redelivered by _defer
            return await self._defer(msg, run_id, delivery, exc)
        context: JobContext
        if descriptor.kind == "workflow":
            context = FlowContext(
                run_id,
                descriptor.name,
                attempt,
                trigger,
                payload,
                runtime=self._flow_runtime,
                fired_at=fired_at,
            )
        else:
            context = JobContext(run_id, descriptor.name, attempt, trigger, payload)
        self._running[run_id] = context
        heartbeat = asyncio.create_task(self._heartbeat(msg))
        progress = asyncio.create_task(self._persist_progress(context))
        work = asyncio.create_task(handler(context))
        self._work[run_id] = work
        timeout = descriptor.timeout.total_seconds() if descriptor.timeout else None
        result: Any = None
        error = ""
        retryable = True
        try:
            done, _ = await asyncio.wait(
                {work, heartbeat}, timeout=timeout, return_when=asyncio.FIRST_COMPLETED
            )
            if heartbeat in done:
                logger.error(
                    "Job acknowledgement heartbeat failed",
                    exc_info=heartbeat.exception(),
                )
                context.cancelled.set()
                work.cancel()
                await asyncio.gather(work, return_exceptions=True)
                status, error = "FAILED", "Acknowledgement heartbeat failed"
            elif not done:
                context.cancelled.set()
                work.cancel()
                with contextlib.suppress(BaseException):
                    await work
                status, error = "TIMED_OUT", f"Timed out after {timeout:g}s"
            elif run_id in self._interrupted:
                status, error = "FAILED", "Interrupted by host shutdown"
            elif context.cancelled.is_set():
                status = "CANCELLED"
            elif work.cancelled():
                status, error = "FAILED", "Job task was cancelled"
            elif work.exception() is not None:
                status, error = (
                    "FAILED",
                    f"{type(work.exception()).__name__}: {work.exception()}",
                )
                # A bad input, an oversized result: no attempt would do better.
                retryable = not isinstance(work.exception(), NonRetryable)
            else:
                result = self._result(work.result())
                status = "SKIPPED" if context.skipped is not None else "SUCCEEDED"
            if (
                status not in ("SUCCEEDED", "SKIPPED", "CANCELLED")
                and attempt < descriptor.max_attempts
                and retryable
            ):
                status = "RETRYING"
            retry_delay = self._backoff(attempt)
            if status == "RETRYING" and _expires_within(msg, retry_delay):
                # JetStream would never redeliver it: the run would stay RETRYING.
                status = "FAILED"
                error = f"Trigger expired before it could be retried; {error}"
            if isinstance(context, FlowContext):
                # A cancelled run cancels its running children.
                await context.finish(status)
            fields: dict[str, Any] = {
                "status": status,
                "logs": list(context.logs),
                "error": error,
            }
            if status == "RETRYING":
                retry_at = datetime.now(timezone.utc) + timedelta(seconds=retry_delay)
                fields["retry_at"] = retry_at.isoformat()
            if status in TERMINAL_STATUSES:
                fields["finished_at"] = _now()
            if status in ("SUCCEEDED", "SKIPPED"):
                fields["result"] = result
            if status == "SKIPPED":
                fields["skip_reason"] = context.skipped
            # A failed heartbeat has already stopped the handler; persist that failure
            # without using the failed renewal task to guard completion retries.
            if heartbeat.done():
                await self._save(run_id, fields)
            else:
                await self._save_completion(run_id, fields, heartbeat)
            if status in TERMINAL_STATUSES:
                await self._notify(descriptor, run_id, status)
            # Persist liveness until completion is durable, then stop before redelivery.
            progress.cancel()
            await asyncio.gather(progress, return_exceptions=True)
            if status == "RETRYING":
                await msg.nak(delay=retry_delay)
            else:
                await self._retire(msg, status)
            return status
        finally:
            context.cancelled.set()
            if isinstance(context, FlowContext):
                await context.close()
            for task in (heartbeat, progress, work):
                task.cancel()
            await asyncio.gather(heartbeat, progress, work, return_exceptions=True)
            self._running.pop(run_id, None)
            self._work.pop(run_id, None)
            self._interrupted.discard(run_id)
