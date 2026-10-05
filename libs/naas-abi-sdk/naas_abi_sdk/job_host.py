"""Runs a module's jobs: schedules, JetStream consumers, event bridges and run records.

One durable pull consumer per job is shared by every replica, so each trigger
reaches one replica; ``max_ack_pending`` bounds concurrency across replicas.
Delivery is at-least-once: a crash or missed ack redelivers the trigger.
Finished run records are pruned (``JobRetention``); active ones never are.
A run whose host stopped on its last attempt is never redelivered, so the
host's upkeep fails it once its heartbeats stop (``reap_lost_runs``).
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from naas_abi_sdk.jobs import (
    MAX_TRIGGERS,
    TERMINAL_STATUSES,
    TRIGGER_HEADER,
    Cron,
    Every,
    JobContext,
    JobDescriptor,
    JobProxy,
    JobRetention,
    JobRun,
    OnEvent,
    job_subjects,
    run_key,
    runs_collection,
    stream_name,
)
from naas_abi_sdk.services.errors import DocumentNotFound, VersionConflict
from naas_abi_sdk.services.models import CollectionSpec, FieldSpec
from naas_abi_sdk.telemetry import current_trace_id, record_error, server_span

logger = logging.getLogger(__name__)

MAX_RESULT_BYTES = 64 * 1024
MANUAL_TRIGGER_TTL = "168h"
EVENT_TRIGGER_TTL = "24h"
MAX_SCHEDULED_TICK_TTL_SECONDS = 3600
DEFAULT_RETENTION = JobRetention()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fired_at(msg: Any) -> str:
    """When JetStream stored the trigger (its schedule fired, or someone triggered it)."""
    stamp = getattr(getattr(msg, "metadata", None), "timestamp", None)
    if isinstance(stamp, datetime):
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return stamp.astimezone(timezone.utc).isoformat()
    return _now()


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
        retention: JobRetention | None = DEFAULT_RETENTION,
        lost_after_seconds: float = 300.0,
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
        self.retention = retention
        self.lost_after_seconds = lost_after_seconds
        self.collection = runs_collection(project)
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

    # --- lifecycle -----------------------------------------------------------------------

    async def start(self) -> None:
        from nats.js.api import AckPolicy, ConsumerConfig, DeliverPolicy

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
        raw = await claim_check.resolve(nc, msg)
        try:
            data: Any = json.loads(raw) if raw else None
        except (ValueError, UnicodeDecodeError):
            data = raw.decode(errors="replace")
        if trigger is not None and not trigger.matches(data):
            return
        stream = stream_name(self.project)
        headers = {TRIGGER_HEADER: "event", "Nats-TTL": EVENT_TRIGGER_TTL}
        event_id = (getattr(msg, "headers", None) or {}).get("Nats-Msg-Id")
        if event_id:
            identity = json.dumps(
                [self._subjects(descriptor).trigger, msg.subject, event_id]
            )
            headers["Nats-Msg-Id"] = hashlib.sha256(identity.encode()).hexdigest()
        body, headers = await claim_check.prepare(
            nc,
            json.dumps({"subject": msg.subject, "data": data}).encode(),
            headers,
            reserve=claim_check.stream_header_reserve(stream),
        )
        await js.publish(
            self._subjects(descriptor).trigger, body, headers=headers, stream=stream
        )

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
        return await JobProxy(
            self.transport, self.project, self.module_id, descriptor, self.documents
        ).trigger(payload, idempotency_key=idempotency_key)

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
        """Fail the runs lost with their host; returns how many.

        A RUNNING run on its last attempt whose heartbeats stopped more than
        ``lost_after_seconds`` ago is never redelivered (``max_deliver``), so
        nothing else would ever finish its record. Runs with attempts left are
        JetStream's: their redelivery updates the record.
        """
        now = now or datetime.now(timezone.utc)
        cutoff = (now - timedelta(seconds=self.lost_after_seconds)).isoformat()
        reaped = 0
        for name in self.handlers:
            page = await self.documents.find(
                self.collection,
                where=[("job", "eq", name), ("status", "eq", "RUNNING")],
                limit=1000,
            )
            for doc in page.items:
                run = doc.data
                last_seen = run.get("heartbeat_at") or run.get("started_at") or ""
                if (
                    doc.id in self._running
                    or run.get("attempt", 1) < run.get("max_attempts", 1)
                    or not last_seen
                    or last_seen >= cutoff
                ):
                    continue
                try:
                    await self.documents.put(
                        self.collection,
                        doc.id,
                        {
                            **run,
                            "status": "FAILED",
                            "error": f"Lost: no heartbeat since {last_seen} "
                            "(its host stopped before the run finished)",
                            "finished_at": now.isoformat(),
                        },
                        if_version=doc.version,
                    )
                    reaped += 1
                except (DocumentNotFound, VersionConflict):
                    continue  # its host is alive after all, or another replica reaped it
        return reaped

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
                )
            if budget <= 0:
                return retention.batch
            finished = [("job", "eq", name), ("status", "in", list(TERMINAL_STATUSES))]
            excess = await self.documents.count(self.collection, finished) - (
                retention.max_runs_per_job
            )
            if excess > 0:
                budget -= await self._delete(
                    finished, min(excess, budget), order_by=("finished_at", "asc")
                )
        return retention.batch - budget

    async def _delete(self, where: list, limit: int, order_by: Any = None) -> int:
        page = await self.documents.find(
            self.collection, where=where, order_by=order_by, limit=min(limit, 1000)
        )
        deleted = 0
        for doc in page.items[:limit]:
            try:
                await self.documents.delete(
                    self.collection, doc.id, if_version=doc.version
                )
                deleted += 1
            except (DocumentNotFound, VersionConflict):
                continue  # another replica pruned or updated it
        return deleted

    async def _on_cancel(self, msg: Any) -> None:
        self.cancel(msg.data.decode(errors="replace"))

    # --- running one trigger ---------------------------------------------------------------

    def _backoff(self, attempt: int) -> float:
        return min(
            self.backoff_base_seconds * 2 ** (attempt - 1), self.max_backoff_seconds
        )

    async def _save(
        self, run_id: str, fields: dict[str, Any], *, only_running: bool = False
    ) -> None:
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
        while True:
            if heartbeat.done():
                await heartbeat
            try:
                await self._save(run_id, fields)
                return
            except Exception:
                logger.warning(
                    "Job completion persistence failed; retrying", exc_info=True
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
            "abi.job.attempt": msg.metadata.num_delivered,
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

    async def _handle_delivery(
        self, descriptor: JobDescriptor, handler: Any, msg: Any
    ) -> str:
        sequence, attempt = msg.metadata.sequence.stream, msg.metadata.num_delivered
        run_id = run_key(descriptor.name, sequence)
        try:
            existing = await self.documents.get(self.collection, run_id)
        except DocumentNotFound:
            pass
        else:
            if existing.data.get("status") in TERMINAL_STATUSES:
                status = existing.data["status"]
                await self._retire(msg, status)
                return status
        headers = msg.headers or {}
        trigger = {"kind": headers.get(TRIGGER_HEADER, "manual")}
        if headers.get("Nats-Scheduler"):
            trigger["scheduler"] = headers["Nats-Scheduler"]
        from naas_abi_sdk import claim_check

        data = msg.data
        if claim_check.carries_reference(msg):
            data = await claim_check.resolve(await self.transport.connect(), msg)
        try:
            payload = json.loads(data) if data else {}
        except (ValueError, UnicodeDecodeError):
            payload = {"raw": data.decode(errors="replace")}
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
                "fired_at": _fired_at(msg),
                "started_at": _now(),
                "heartbeat_at": _now(),
                "trace_id": current_trace_id(),
                "error": "",
            },
        )
        self._running[run_id] = context
        heartbeat = asyncio.create_task(self._heartbeat(msg))
        progress = asyncio.create_task(self._persist_progress(context))
        work = asyncio.create_task(handler(context))
        self._work[run_id] = work
        timeout = descriptor.timeout.total_seconds() if descriptor.timeout else None
        result: Any = None
        error = ""
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
            else:
                result = self._result(work.result())
                status = "SKIPPED" if context.skipped is not None else "SUCCEEDED"
            if (
                status not in ("SUCCEEDED", "SKIPPED", "CANCELLED")
                and attempt < descriptor.max_attempts
            ):
                status = "RETRYING"
            fields: dict[str, Any] = {
                "status": status,
                "logs": list(context.logs),
                "error": error,
            }
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
            # Persist liveness until completion is durable, then stop before redelivery.
            progress.cancel()
            await asyncio.gather(progress, return_exceptions=True)
            if status == "RETRYING":
                await msg.nak(delay=self._backoff(attempt))
            else:
                await self._retire(msg, status)
            return status
        finally:
            context.cancelled.set()
            for task in (heartbeat, progress, work):
                task.cancel()
            await asyncio.gather(heartbeat, progress, work, return_exceptions=True)
            self._running.pop(run_id, None)
            self._work.pop(run_id, None)
            self._interrupted.discard(run_id)
