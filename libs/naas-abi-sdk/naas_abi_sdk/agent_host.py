"""Provider-side agent hosting. Only data crosses the network boundary."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import partial
from typing import Any, Protocol

from google.protobuf.message import DecodeError
from naas_abi_proto.agent.v1 import agent_pb2 as pb
from naas_abi_proto.discovery.v1 import discovery_pb2 as discovery_pb

from naas_abi_sdk import overflow
from naas_abi_sdk.agent import TERMINAL, agent_subject
from naas_abi_sdk.messages import reply
from naas_abi_sdk.services.errors import DocumentNotFound, VersionConflict
from naas_abi_sdk.services.models import CollectionSpec
from naas_abi_sdk.telemetry import current_trace_id, internal_span, server_span
from naas_abi_sdk.transport import RPCError

# Where a submitter may ask for RunUpdates: its own inbox, never a service subject.
UPDATES_INBOX = re.compile(r"_INBOX\.[A-Za-z0-9_.-]{1,240}")
# Event data pushed inline up to this (and a quarter of the broker limit);
# above it only the part count, which the submitter reads with EventRequest.
INLINE_UPDATE_BYTES = 32 * 1024


@dataclass
class InvocationContext:
    invocation_id: str
    thread_id: str
    caller_identity: str
    cancelled: asyncio.Event = field(default_factory=asyncio.Event)


class AgentHandler(Protocol):
    async def invoke(self, prompt: str, context: InvocationContext) -> str: ...


@dataclass
class _Run:
    key: str
    data: dict[str, Any]
    version: int
    context: InvocationContext
    lock_key: str
    lock_version: int
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    task: asyncio.Task | None = None
    deadline: asyncio.Task | None = None
    watchdog: asyncio.Task | None = None
    progress_at: float = 0
    cancel_reason: str = ""
    started: asyncio.Event = field(default_factory=asyncio.Event)
    watchers: set[str] = field(default_factory=set)  # inboxes receiving RunUpdates


def _hash(*values: str) -> str:
    return hashlib.sha256(json.dumps(values, ensure_ascii=True).encode()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def agent_runs_collection(project: str) -> str:
    """Where a module's agent hosts keep one record per invocation (in the
    module's document namespace)."""
    return f"agent_runs_{_hash(project)[:16]}"


def agent_events_collection(project: str) -> str:
    """Where those invocations' events and output fragments are kept."""
    return f"agent_events_{_hash(project)[:16]}"


def _error(code: str, message: str) -> RPCError:
    return RPCError(code, message)


class AgentHost:
    """Durable no-replay execution, with conversation claims that never auto-expire.

    Orphaned claims require operator reconciliation after proving the old process
    has stopped. Membership expiry is deliberately not execution ownership transfer.
    """

    def __init__(
        self,
        session,
        documents,
        handlers: dict[str, AgentHandler],
        *,
        idle_timeout_seconds: float = 300.0,
    ):
        if not math.isfinite(idle_timeout_seconds) or idle_timeout_seconds <= 0:
            raise ValueError("Agent inactivity timeout must be positive and finite")
        self.idle_timeout_seconds = idle_timeout_seconds
        self.session, self.documents, self.handlers = session, documents, handlers
        suffix = _hash(session.client.project)[:16]
        self.runs_collection = agent_runs_collection(session.client.project)
        self.locks_collection = f"agent_claims_{suffix}"
        self.events_collection = agent_events_collection(session.client.project)
        self._membership = (0.0, set())
        self._membership_lock = asyncio.Lock()
        self.runs: dict[str, _Run] = {}
        self.subscriptions = []
        self.accept_lock = asyncio.Lock()
        self.closing = False

    async def start(self) -> None:
        for name in (
            self.runs_collection,
            self.locks_collection,
            self.events_collection,
        ):
            await self.documents.ensure_collection(CollectionSpec(name=name))
        async with self.session._lock:
            self.session.on_registered = self._bind
            await self._bind()

    async def _bind(self) -> None:
        nc = await self.session.client.transport.connect()
        pending = []
        try:
            for name in self.handlers:
                for operation in ("submit", "status", "cancel", "event"):
                    pending.append(
                        await nc.subscribe(
                            agent_subject(
                                self.session.client.project,
                                self.session.instance_id,
                                name,
                                operation,
                            ),
                            cb=partial(self._handle, name, operation),
                        )
                    )
            await nc.flush()
        except BaseException:
            for sub in pending:
                await sub.unsubscribe()
            raise
        old, self.subscriptions = self.subscriptions, pending
        self._membership = (0.0, set())
        for sub in old:
            await sub.drain()

    async def _authorize(
        self, name: str, token: str, new_invocation: bool
    ) -> tuple[str, bool]:
        """The caller's identity, and whether it is a platform administrator
        (discovery's admin identities), as discovery vouches for both."""
        response = await self.session.client._call(
            "authorize_agent",
            discovery_pb.AuthorizeAgentRequest(
                instance_id=self.session.instance_id,
                lease_token=self.session.lease_token,
                agent_name=name,
                caller_token=token,
                new_invocation=new_invocation,
            ),
            discovery_pb.AuthorizeAgentResponse,
        )
        return response.caller_identity, response.caller_admin

    async def _handle(self, name: str, operation: str, msg) -> None:
        # Runs started by a submit inherit this span (their task copies the context).
        with server_span(msg.subject, msg.headers, attributes={"abi.agent.name": name}):
            await self._handle_operation(name, operation, msg)

    async def _handle_operation(self, name: str, operation: str, msg) -> None:
        cls = getattr(pb, operation.title() + "Request")
        response_cls = getattr(pb, operation.title() + "Response")
        response = response_cls()
        try:
            # An overflow upload is above the broker limit, so above this cap too.
            if len(msg.data) > 128 * 1024 or overflow.REQUEST_HEADER in (
                msg.headers or {}
            ):
                raise _error("PAYLOAD_TOO_LARGE", "Agent request exceeds 128 KiB")
            req = cls.FromString(msg.data)
            if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", req.invocation_id):
                raise _error("INVALID_ARGUMENT", "Invalid invocation ID")
            caller, admin = await self._authorize(
                name,
                (msg.headers or {}).get("Nats-Auth-Token", ""),
                operation == "submit",
            )
            if operation != "event" and req.output_format != 2:
                raise _error(
                    "UPGRADE_REQUIRED",
                    "Agent output requires an SDK supporting output_format=2",
                )
            key = _hash(name, req.invocation_id)
            if operation == "submit":
                doc = await self._submit(name, key, caller, req)
            else:
                doc = await self.documents.get(self.runs_collection, key)
                # Platform administrators may stop any run (the System app),
                # never read another caller's output.
                if doc.data["caller"] != caller and not (
                    admin and operation == "cancel"
                ):
                    raise _error(
                        "PERMISSION_DENIED", "Invocation belongs to another caller"
                    )
                if operation == "event":
                    last = doc.data.get(
                        "last_sequence", len(doc.data.get("events", []))
                    )
                    if req.sequence > last or (
                        req.sequence == 0 and doc.data["status"] != "SUCCEEDED"
                    ):
                        raise _error("NOT_FOUND", "Output is not committed")
                    fragment = await self.documents.get(
                        self.events_collection, f"{key}:{req.sequence}:{req.part}"
                    )
                    await reply(
                        msg,
                        pb.EventResponse(
                            data=fragment.data["data"]
                        ).SerializeToString(),
                    )
                    return
                if operation == "cancel" and doc.data["status"] not in TERMINAL:
                    run = self.runs.get(key)
                    if run is None:
                        raise _error(
                            "OWNER_UNAVAILABLE",
                            "This process does not own execution; cancellation is not inferred from lease expiry",
                        )
                    await self._cancel(run, "CANCELLED")
                    doc = await self.documents.get(self.runs_collection, key)
            response.invocation.CopyFrom(
                await self._view(doc.data, getattr(req, "after_sequence", 0))
            )
        except DecodeError:
            response.error.code, response.error.message = (
                "INVALID_ARGUMENT",
                "Malformed protobuf",
            )
        except DocumentNotFound:
            response.error.code, response.error.message = (
                "INVOCATION_NOT_FOUND",
                "Invocation not found",
            )
        except RPCError as exc:
            response.error.code, response.error.message = exc.code, str(exc)
        except Exception:
            logging.getLogger(__name__).exception("Agent RPC failed")
            response.error.code, response.error.message = (
                "UNAVAILABLE",
                "Agent operation failed; reconcile submission by invocation ID",
            )
        payload = response.SerializeToString()
        nc = await self.session.client.transport.connect()
        if len(payload) > min(nc.max_payload, 512 * 1024):
            response = response_cls()
            response.error.code, response.error.message = (
                "PAYLOAD_TOO_LARGE",
                "Agent response exceeds limit",
            )
            payload = response.SerializeToString()
        if msg.reply:
            await reply(msg, payload)

    async def _view(self, data: dict, after: int = 0) -> pb.Invocation:
        now = asyncio.get_running_loop().time()
        async with self._membership_lock:
            if now >= self._membership[0]:
                instances = await self.session.client.get_module(
                    self.session.descriptor.module_id,
                    self.session.descriptor.contract_major,
                )
                self._membership = (now + 1.0, {i.instance_id for i in instances})
        events = []
        last = data.get("last_sequence", len(data.get("events", [])))
        if data.get("output_format") == 2:
            key = _hash(data["agent_name"], data["invocation_id"])
            for sequence in range(after + 1, min(last, after + 64) + 1):
                manifest = await self.documents.get(
                    self.events_collection, f"{key}:{sequence}"
                )
                events.append(
                    pb.AgentEvent(
                        sequence=sequence,
                        event=manifest.data["event"],
                        parts=manifest.data["parts"],
                    )
                )
        else:
            events = [
                pb.AgentEvent(sequence=i + 1, event=e["event"], data=e["data"])
                for i, e in enumerate(data["events"])
                if i + 1 > after
            ][:64]
        state = (
            "FINALIZING"
            if data["status"] in TERMINAL
            and _hash(data["agent_name"], data["invocation_id"]) in self.runs
            else data["status"]
        )
        return pb.Invocation(
            invocation_id=data["invocation_id"],
            thread_id=data["thread_id"],
            status=state,
            result=data.get("result", ""),
            error_code=data.get("error_code", ""),
            error_message=data.get("error_message", ""),
            owner_instance_id=data["owner"],
            owner_available=data["owner"] in self._membership[1],
            events=events,
            last_sequence=last,
            result_parts=data.get("result_parts", 0),
        )

    async def _submit(self, name: str, key: str, caller: str, req):
        if (
            not req.thread_id
            or len(req.thread_id) > 256
            or len(req.prompt.encode()) > 64 * 1024
            or req.mode not in ("invoke", "stream")
            or not 0 <= req.deadline_seconds <= 3600
        ):
            raise _error("INVALID_ARGUMENT", "Invalid thread, prompt, mode or deadline")
        if req.updates_inbox and not UPDATES_INBOX.fullmatch(req.updates_inbox):
            raise _error("INVALID_ARGUMENT", "Updates go to an _INBOX subject only")
        fingerprint = _hash(
            caller, req.thread_id, req.prompt, req.mode, str(req.deadline_seconds)
        )
        async with self.accept_lock:
            try:
                existing = await self.documents.get(self.runs_collection, key)
            except DocumentNotFound:
                existing = None
            if existing:
                if existing.data["caller"] != caller:
                    raise _error(
                        "PERMISSION_DENIED", "Invocation belongs to another caller"
                    )
                if existing.data["fingerprint"] != fingerprint:
                    raise _error(
                        "INVOCATION_CONFLICT",
                        "Invocation ID reused with different input",
                    )
                self._watch(key, req.updates_inbox)
                return existing
            if self.closing or len(self.runs) >= 32:
                raise _error(
                    "AGENT_BUSY", "Provider is draining or at execution capacity"
                )
            data = {
                "agent_name": name,
                "invocation_id": req.invocation_id,
                "thread_id": req.thread_id,
                "caller": caller,
                "fingerprint": fingerprint,
                "owner": self.session.instance_id,
                "status": "ACCEPTED",
                "events": [],
                "output_format": 2,
                "last_sequence": 0,
                "result_parts": 0,
                "result": "",
                "error_code": "",
                "error_message": "",
                "submitted_at": _now(),
                "trace_id": current_trace_id(),
            }
            try:
                doc = await self.documents.put(
                    self.runs_collection, key, data, if_version=0
                )
            except VersionConflict:
                existing = await self.documents.get(self.runs_collection, key)
                if (
                    existing.data["caller"] != caller
                    or existing.data["fingerprint"] != fingerprint
                ):
                    raise _error(
                        "INVOCATION_CONFLICT",
                        "Invocation ID already exists with different input",
                    )
                return existing
            lock_key = _hash(name, caller, req.thread_id)
            try:
                claim = await self.documents.put(
                    self.locks_collection,
                    lock_key,
                    {"invocation_key": key, "owner": self.session.instance_id},
                    if_version=0,
                )
            except VersionConflict:
                data.update(
                    status="FAILED",
                    error_code="CONVERSATION_BUSY",
                    error_message="Conversation has an active or unresolved execution claim",
                    finished_at=_now(),
                )
                return await self.documents.put(
                    self.runs_collection, key, data, if_version=doc.version
                )
            data["status"] = "RUNNING"
            doc = await self.documents.put(
                self.runs_collection, key, data, if_version=doc.version
            )
            context = InvocationContext(
                req.invocation_id,
                _hash(
                    self.session.client.project,
                    self.session.descriptor.module_id,
                    name,
                    caller,
                    req.thread_id,
                ),
                caller,
            )
            run = _Run(key, data, doc.version, context, lock_key, claim.version)
            if req.updates_inbox:
                run.watchers.add(req.updates_inbox)
            run.progress_at = asyncio.get_running_loop().time()
            self.runs[key] = run
            run.task = asyncio.create_task(self._execute(name, req, run))
            run.task.add_done_callback(self._observe_task)
            run.watchdog = asyncio.create_task(self._watch_progress(run))
            run.watchdog.add_done_callback(self._observe_task)
            if req.deadline_seconds:
                run.deadline = asyncio.create_task(
                    self._deadline(run, req.deadline_seconds)
                )
                run.deadline.add_done_callback(self._observe_task)
            return doc

    @staticmethod
    def _observe_task(task: asyncio.Task) -> None:
        if not task.cancelled() and task.exception() is not None:
            logging.getLogger(__name__).error(
                "Agent task stopped without durable completion; reconcile its claim",
                exc_info=task.exception(),
            )

    async def _save(self, run: _Run, **updates) -> None:
        async with run.lock:
            if updates.get("status") == "CANCELLING" and run.data["status"] in TERMINAL:
                return
            if updates.get("status") == "SUCCEEDED" and run.context.cancelled.is_set():
                raise asyncio.CancelledError()
            if updates.get("status") in TERMINAL:
                updates.setdefault("finished_at", _now())
            candidate = run.data | updates
            if len(json.dumps(candidate).encode()) > 384 * 1024:
                raise _error("OUTPUT_LIMIT", "Invocation record exceeds 384 KiB")
            doc = await self.documents.put(
                self.runs_collection, run.key, candidate, if_version=run.version
            )
            run.data, run.version = candidate, doc.version

    async def _store_output(self, run: _Run, sequence: int, text: str) -> int:
        payload = text.encode()
        size = 8192
        parts = max(1, (len(payload) + size - 1) // size)
        for part in range(parts):
            await self.documents.put(
                self.events_collection,
                f"{run.key}:{sequence}:{part}",
                {"data": payload[part * size : (part + 1) * size]},
                if_version=0,
            )
            run.progress_at = asyncio.get_running_loop().time()
        return parts

    async def _event(self, run: _Run, event: dict) -> None:
        if run.context.cancelled.is_set():
            raise asyncio.CancelledError()
        if (
            set(event) != {"event", "data"}
            or not all(isinstance(v, str) for v in event.values())
            or len(event["event"]) > 64
        ):
            raise _error("INVALID_STREAM", "Events must contain event/data strings")
        sequence = run.data["last_sequence"] + 1
        parts = await self._store_output(run, sequence, event["data"])
        await self.documents.put(
            self.events_collection,
            f"{run.key}:{sequence}",
            {"event": event["event"], "parts": parts},
            if_version=0,
        )
        # Publish the cursor only after every immutable fragment has committed.
        await self._save(run, last_sequence=sequence)
        run.progress_at = asyncio.get_running_loop().time()
        await self._push(run, event, sequence, parts)

    def _watch(self, key: str, inbox: str) -> None:
        run = self.runs.get(key)
        if run is not None and inbox:
            run.watchers.add(inbox)

    async def _push(
        self, run: _Run, event: dict | None = None, sequence: int = 0, parts: int = 0
    ) -> None:
        """Tell the run's watchers what just committed: an event, or with no
        event the terminal status. Hints only (at most once, core NATS): the
        Status reply stays authoritative, so a failed push never fails the run."""
        if not run.watchers:
            return
        try:
            nc = await self.session.client.transport.connect()
            if event is None:
                update = pb.RunUpdate(
                    status=run.data["status"],
                    last_sequence=run.data["last_sequence"],
                )
            else:
                limit = min(INLINE_UPDATE_BYTES, nc.max_payload // 4)
                inline = len(event["data"].encode()) <= limit
                update = pb.RunUpdate(
                    event=pb.AgentEvent(
                        sequence=sequence,
                        event=event["event"],
                        data=event["data"] if inline else "",
                        parts=0 if inline else parts,
                    )
                )
            payload = update.SerializeToString()
            for inbox in tuple(run.watchers):
                await nc.publish(inbox, payload)
        except Exception:  # watchers fall back to Status
            logging.getLogger(__name__).debug(
                "Run update not delivered; watchers read the status", exc_info=True
            )

    async def _execute(self, name: str, req, run: _Run) -> None:
        with internal_span(
            f"agent {name} run",
            {"abi.agent.name": name, "abi.agent.invocation_id": req.invocation_id},
        ):
            await self._execute_run(name, req, run)

    async def _execute_run(self, name: str, req, run: _Run) -> None:
        completed = False
        run.started.set()
        try:
            handler = self.handlers[name]
            if req.mode == "stream" and hasattr(handler, "stream_invoke"):
                messages = []
                done = False
                stream = handler.stream_invoke(req.prompt, run.context)
                try:
                    async for event in stream:
                        if done:
                            raise _error("INVALID_STREAM", "Agent emitted after done")
                        await self._event(run, event)
                        if event["event"] == "message":
                            messages.append(event["data"])
                        done = event["event"] == "done"
                finally:
                    if hasattr(stream, "aclose"):
                        await stream.aclose()
                result = "\n".join(messages)
                if not done:
                    await self._event(run, {"event": "done", "data": "[DONE]"})
            else:
                result = await handler.invoke(req.prompt, run.context)
                if not isinstance(result, str):
                    raise _error("OUTPUT_LIMIT", "Agent result must be text")
                await self._event(run, {"event": "message", "data": result})
                await self._event(run, {"event": "done", "data": "[DONE]"})
            parts = await self._store_output(run, 0, result)
            await self._save(run, status="SUCCEEDED", result_parts=parts)
            completed = True
        except asyncio.CancelledError:
            await self._save(
                run,
                status=run.cancel_reason or "CANCELLED",
                error_code=run.cancel_reason or "CANCELLED",
                error_message="Execution stopped; completed side effects are not undone",
            )
            completed = True
        except Exception as exc:
            logging.getLogger(__name__).exception("Agent execution failed")
            await self._save(
                run,
                status="FAILED",
                error_code=exc.code if isinstance(exc, RPCError) else "AGENT_FAILED",
                error_message="Agent execution failed; inspect provider logs",
            )
            completed = True
        finally:
            if run.watchdog and run.watchdog is not asyncio.current_task():
                run.watchdog.cancel()
            if run.deadline and run.deadline is not asyncio.current_task():
                run.deadline.cancel()
            if completed:
                try:
                    await self.documents.delete(
                        self.locks_collection, run.lock_key, if_version=run.lock_version
                    )
                except RPCError:
                    logging.getLogger(__name__).exception(
                        "Conversation claim release failed; reconcile before another run"
                    )
            self.runs.pop(run.key, None)
            if completed:
                # After leaving self.runs: a Status read now reports the end.
                await self._push(run)

    async def _cancel(self, run: _Run, reason: str) -> None:
        if run.task and not run.task.done() and not run.context.cancelled.is_set():
            await run.started.wait()
            if run.data["status"] in TERMINAL:
                return
            run.cancel_reason = reason
            run.context.cancelled.set()
            await self._save(run, status="CANCELLING")
            if run.data["status"] not in TERMINAL:
                run.task.cancel()

    async def _watch_progress(self, run: _Run) -> None:
        while True:
            remaining = self.idle_timeout_seconds - (
                asyncio.get_running_loop().time() - run.progress_at
            )
            if remaining <= 0:
                await self._cancel(run, "TIMED_OUT")
                return
            await asyncio.sleep(remaining)

    async def _deadline(self, run: _Run, seconds: int) -> None:
        await asyncio.sleep(seconds)
        await self._cancel(run, "TIMED_OUT")

    async def close(self) -> None:
        self.closing = True
        self.session.on_registered = None
        for sub in self.subscriptions:
            await sub.drain()
        self.subscriptions.clear()
        runs = list(self.runs.values())
        for run in runs:
            await self._cancel(run, "CANCELLED")
        await asyncio.gather(*(r.task for r in runs if r.task), return_exceptions=True)
