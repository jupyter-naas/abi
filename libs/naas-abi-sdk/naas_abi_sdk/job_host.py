"""Runs a module's jobs: schedules, JetStream consumers, event bridges and run records.

One durable pull consumer per job is shared by every replica, so each trigger
reaches one replica; ``max_ack_pending`` bounds concurrency across replicas.
Delivery is at-least-once: a crash or missed ack redelivers the trigger.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from naas_abi_sdk.jobs import (
    MAX_TRIGGERS,
    TERMINAL_STATUSES,
    TRIGGER_HEADER,
    Cron,
    Every,
    JobContext,
    JobDescriptor,
    job_subjects,
    run_key,
    runs_collection,
    stream_name,
)
from naas_abi_sdk.services.errors import DocumentNotFound, VersionConflict
from naas_abi_sdk.services.models import CollectionSpec

logger = logging.getLogger(__name__)

MAX_RESULT_BYTES = 64 * 1024
MANUAL_TRIGGER_TTL = "168h"
EVENT_TRIGGER_TTL = "24h"
MAX_SCHEDULED_TICK_TTL_SECONDS = 3600


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _seconds(go_duration: str) -> float:
    units = {"ns": 1e-9, "us": 1e-6, "µs": 1e-6, "ms": 1e-3, "s": 1, "m": 60, "h": 3600}
    return sum(
        float(n) * units[u]
        for n, u in re.findall(r"(\d+(?:\.\d+)?)(ns|us|µs|ms|s|m|h)", go_duration)
    )


def scheduled_tick_ttl(trigger: Cron | Every) -> str:
    """Unprocessed ticks expire: a module back after days runs once, not per missed tick."""
    if isinstance(trigger, Every):
        ttl = max(60, min(_seconds(trigger.interval), MAX_SCHEDULED_TICK_TTL_SECONDS))
    else:
        ttl = MAX_SCHEDULED_TICK_TTL_SECONDS
    return f"{int(ttl)}s"


async def ensure_stream(js: Any, project: str) -> None:
    """Create the project's jobs stream (schedules + TTL) or enable the flags on it."""
    from nats.js.api import StreamConfig
    from nats.js.errors import BadRequestError, NotFoundError

    name = stream_name(project)
    config = StreamConfig(
        name=name,
        subjects=[f"abi.jobs.{project}.>"],
        allow_msg_schedules=True,
        allow_msg_ttl=True,
    )
    try:
        info = await js.stream_info(name)
    except NotFoundError:
        try:
            await js.add_stream(config)
            return
        except BadRequestError:
            info = await js.stream_info(name)
    current = info.config
    if not (current.allow_msg_schedules and current.allow_msg_ttl):
        current.allow_msg_schedules = True
        current.allow_msg_ttl = True
        await js.update_stream(current)


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
    ):
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
        self.collection = runs_collection(project)
        self._running: dict[str, JobContext] = {}
        self._work: dict[str, asyncio.Task] = {}
        # Runs stopped by close(): retried elsewhere, never recorded as user cancels.
        self._interrupted: set[str] = set()
        self._tasks: set[asyncio.Task] = set()
        self._loops: list[asyncio.Task] = []
        self._subscriptions: list[Any] = []
        self._closing = False

    def _subjects(self, descriptor: JobDescriptor):
        return job_subjects(self.project, self.module_id, descriptor.name)

    # --- lifecycle -----------------------------------------------------------------------

    async def start(self) -> None:
        from nats.js.api import AckPolicy, ConsumerConfig, DeliverPolicy

        await self.documents.ensure_collection(CollectionSpec(name=self.collection))
        nc = await self.transport.connect()
        js = nc.jetstream()
        await ensure_stream(js, self.project)
        cancel_subject = None
        for descriptor, handler in self.handlers.values():
            subjects = self._subjects(descriptor)
            cancel_subject = subjects.cancel
            await js.add_consumer(
                stream_name(self.project),
                ConsumerConfig(
                    durable_name=subjects.consumer,
                    filter_subject=subjects.trigger,
                    ack_policy=AckPolicy.EXPLICIT,
                    deliver_policy=DeliverPolicy.NEW,
                    ack_wait=self.ack_wait_seconds,
                    max_deliver=descriptor.max_attempts,
                    max_ack_pending=descriptor.max_concurrency,
                ),
            )
            await self.reconcile_schedules(js, descriptor)
            for event in descriptor.events:
                self._subscriptions.append(
                    await nc.subscribe(
                        event.subject,
                        queue=f"{subjects.consumer}-events",
                        cb=self._event_bridge(js, descriptor),
                    )
                )
            sub = await js.pull_subscribe_bind(
                durable=subjects.consumer, stream=stream_name(self.project)
            )
            self._loops.append(
                asyncio.create_task(self._consume(sub, descriptor, handler))
            )
        if cancel_subject:
            self._subscriptions.append(
                await nc.subscribe(cancel_subject, cb=self._on_cancel)
            )

    async def close(self) -> None:
        self._closing = True
        for loop in self._loops:
            loop.cancel()
        await asyncio.gather(*self._loops, return_exceptions=True)
        for subscription in self._subscriptions:
            with contextlib.suppress(Exception):
                await subscription.unsubscribe()
        for run_id, context in self._running.items():
            self._interrupted.add(run_id)
            context.cancelled.set()
        if not self._tasks:
            return
        _, pending = await asyncio.wait(
            set(self._tasks), timeout=self.close_grace_seconds
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
        while not self._closing:
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
        """One schedule message per Cron/Every trigger; stale indexes are purged."""
        subjects = self._subjects(descriptor)
        schedules = descriptor.schedules
        for index, trigger in enumerate(schedules):
            headers = {
                **trigger.headers(),
                "Nats-Schedule-Target": subjects.trigger,
                "Nats-Schedule-TTL": scheduled_tick_ttl(trigger),
                TRIGGER_HEADER: "schedule",
            }
            await js.publish(
                subjects.schedule(index),
                b"{}",
                headers=headers,
                stream=stream_name(self.project),
            )
        for index in range(len(schedules), MAX_TRIGGERS):
            await js.purge_stream(
                stream_name(self.project), subject=subjects.schedule(index)
            )

    async def bridge_event(self, js: Any, descriptor: JobDescriptor, msg: Any) -> None:
        """Republish a core-NATS event as a durable trigger (deduplicated per event)."""
        try:
            data: Any = json.loads(msg.data) if msg.data else None
        except (ValueError, UnicodeDecodeError):
            data = msg.data.decode(errors="replace")
        await js.publish(
            self._subjects(descriptor).trigger,
            json.dumps({"subject": msg.subject, "data": data}).encode(),
            headers={
                TRIGGER_HEADER: "event",
                "Nats-Msg-Id": f"{descriptor.name}:{msg.subject}",
                "Nats-TTL": EVENT_TRIGGER_TTL,
            },
            stream=stream_name(self.project),
        )

    # --- cancellation ------------------------------------------------------------------------

    def cancel(self, run_id: str) -> bool:
        context = self._running.get(run_id)
        if context is None:
            return False
        context.cancelled.set()
        return True

    def _event_bridge(self, js: Any, descriptor: JobDescriptor) -> Any:
        async def on_event(msg: Any) -> None:
            self._spawn(self.bridge_event(js, descriptor, msg))

        return on_event

    async def _on_cancel(self, msg: Any) -> None:
        self.cancel(msg.data.decode(errors="replace"))

    # --- running one trigger ---------------------------------------------------------------

    def _backoff(self, attempt: int) -> float:
        return min(
            self.backoff_base_seconds * 2 ** (attempt - 1), self.max_backoff_seconds
        )

    async def _save(self, run_id: str, fields: dict[str, Any]) -> None:
        for _ in range(3):
            try:
                existing = await self.documents.get(self.collection, run_id)
            except DocumentNotFound:
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
            try:
                await self.documents.put(
                    self.collection,
                    run_id,
                    {**existing.data, **fields},
                    if_version=existing.version,
                )
                return
            except VersionConflict:
                continue
        logger.warning("Could not save job run %s after concurrent updates", run_id)

    async def _heartbeat(self, msg: Any, context: JobContext) -> None:
        while True:
            await asyncio.sleep(self.heartbeat_seconds)
            await msg.in_progress()
            await self._save(context.run_id, {"logs": list(context.logs)})

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
        sequence, attempt = msg.metadata.sequence.stream, msg.metadata.num_delivered
        run_id = run_key(descriptor.name, sequence)
        headers = msg.headers or {}
        trigger = {"kind": headers.get(TRIGGER_HEADER, "manual")}
        if headers.get("Nats-Scheduler"):
            trigger["scheduler"] = headers["Nats-Scheduler"]
        try:
            payload = json.loads(msg.data) if msg.data else {}
        except (ValueError, UnicodeDecodeError):
            payload = {"raw": msg.data.decode(errors="replace")}
        if not isinstance(payload, dict):
            payload = {"value": payload}
        context = JobContext(run_id, descriptor.name, attempt, trigger, payload)
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
                "started_at": _now(),
                "error": "",
            },
        )
        self._running[run_id] = context
        heartbeat = asyncio.create_task(self._heartbeat(msg, context))
        work = asyncio.create_task(handler(context))
        self._work[run_id] = work
        timeout = descriptor.timeout.total_seconds() if descriptor.timeout else None
        result: Any = None
        error = ""
        try:
            done, _ = await asyncio.wait({work}, timeout=timeout)
            if not done:
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
            else:
                status, result = "SUCCEEDED", self._result(work.result())
        finally:
            heartbeat.cancel()
            with contextlib.suppress(BaseException):
                await heartbeat
            self._running.pop(run_id, None)
            self._work.pop(run_id, None)
            self._interrupted.discard(run_id)

        if status in ("SUCCEEDED", "CANCELLED"):
            await msg.ack()
        elif attempt < descriptor.max_attempts:
            status = "RETRYING"
            await msg.nak(delay=self._backoff(attempt))
        else:
            await msg.term()
        fields: dict[str, Any] = {
            "status": status,
            "logs": list(context.logs),
            "error": error,
        }
        if status in TERMINAL_STATUSES:
            fields["finished_at"] = _now()
        if status == "SUCCEEDED":
            fields["result"] = result
        await self._save(run_id, fields)
