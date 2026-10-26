"""Durable workflows: a job with a typed input and output, and checkpointed steps.

A workflow is a job (``kind="workflow"``): same consumer, run record, attempts,
cancel and retention (``jobs.py``, ``job_host.py``). Its handler receives a
``FlowContext`` whose ``step`` journals each result, so a retry of the same run
(a crashed host, a deploy, a failed step) returns the stored results of the
steps that finished and runs the rest::

    class ABIModule(BaseModule):
        @workflow(triggers=(Cron("0 0 * * * *", input={"filter": "db"}),))
        async def tweets(self, ctx: FlowContext, inp: TweetsInput) -> TweetsOutput:
            files = await ctx.step("fetch", self.fetch, inp)
            await ctx.map_call("map", "acme.tweets", "map_envelope", [{"path": f} for f in files])
            return TweetsOutput(count=len(files))

Callers: ``ABIClient.get_workflow(module, name).run(input)``, ``ModuleProxy.get_workflow``,
``self.get_workflow(name)``. The decision is in the package's AGENTS.md.

Importable without ``nats`` (stdlib and proto only; the NATS client loads when a
run is waited for or triggered), and without pydantic: input and output types are
duck-typed (``model_json_schema``, ``model_validate``, ``model_dump``).
"""

from __future__ import annotations

import asyncio
import collections.abc
import contextlib
import inspect
import json
import logging
import re
import time
import typing
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from naas_abi_sdk.jobs import (
    TERMINAL_STATUSES,
    JobContext,
    JobDescriptor,
    JobProxy,
    JobRun,
    NonRetryable,
    Trigger,
    _hash,
    is_async_callable,
    job_subjects,
    schema_json,
)

logger = logging.getLogger(__name__)

# A step's journaled result, as JSON. Larger data goes to object storage, and the
# step returns a reference to it.
MAX_STEP_RESULT_BYTES = 256 * 1024
MAX_STEP_KEY_LENGTH = 200
MAX_FAN_OUT = 10_000
DEFAULT_FAN_OUT_CONCURRENCY = 8
# Core NATS is at-most-once: a waiter polls at this pace besides listening for notices.
NOTICE_FALLBACK_POLL_SECONDS = 5.0
# A parent that ends with one of these is not retried: it cancels its children.
STOPPED_PARENT_STATUSES = frozenset({"CANCELLED", "TIMED_OUT", "FAILED"})
# A host's own result cap for a run (job_host.MAX_RESULT_BYTES), as its marker shows.
_TRUNCATED = {"truncated", "preview"}


# --- errors ----------------------------------------------------------------------------


class WorkflowError(Exception):
    """A workflow could not run, or ended without an output."""


class InvalidWorkflowInput(NonRetryable, ValueError):
    """The run's input does not match the workflow's input type."""


class InvalidWorkflowOutput(NonRetryable, ValueError):
    """The handler returned a value that is not its declared output type."""


class StepKeyError(NonRetryable, ValueError):
    """A step key is invalid, or a second step of the same run uses it."""


class StepResultTooLarge(NonRetryable, ValueError):
    """A step result is over ``MAX_STEP_RESULT_BYTES``."""


class StepResultNotJSON(NonRetryable, TypeError):
    """A step result cannot be journaled as JSON."""


class SelfCall(NonRetryable, ValueError):
    """A workflow called itself: its child would wait for the slot its parent holds."""


class ChildOutputTruncated(NonRetryable, WorkflowError):
    """A child's output went over the host's result cap and was cut."""


class WorkflowCancelled(Exception):
    """The run was cancelled (or its host is stopping) while it waited."""


class ChildRunFailed(WorkflowError):
    """A child run ended FAILED, TIMED_OUT or CANCELLED."""


class WorkflowRunFailed(WorkflowError):
    """A run ended without an output (``WorkflowRun.result``)."""

    def __init__(self, run_id: str, status: str, error: str):
        super().__init__(f"Workflow run {run_id} ended {status}: {error}".rstrip(": "))
        self.run_id, self.status, self.error = run_id, status, error


# --- types and schemas -----------------------------------------------------------------


@dataclass(frozen=True)
class WorkflowSpec:
    """The types a workflow's handler takes and returns; None means a plain dict."""

    input_type: Any = None
    output_type: Any = None


# Makes a workflow's job handler of its handler and spec (``declare_workflow(wrap=)``).
HandlerWrap = Callable[[Callable[..., Any], WorkflowSpec], Callable[..., Any]]


def is_model_type(value: Any) -> bool:
    """A pydantic v2 model class, by its methods: pydantic stays optional."""
    return (
        isinstance(value, type)
        and callable(getattr(value, "model_json_schema", None))
        and callable(getattr(value, "model_validate", None))
    )


def _is_model_value(value: Any) -> bool:
    return callable(getattr(value, "model_dump", None)) and not isinstance(value, type)


def _is_dict_type(tp: Any) -> bool:
    origin = typing.get_origin(tp) or tp
    return tp is typing.Any or origin in (dict, collections.abc.Mapping)


def _dump(value: Any) -> Any:
    """A model as JSON-compatible Python; anything else as it is."""
    if _is_model_value(value):
        try:
            return value.model_dump(mode="json")
        except TypeError:
            return value.model_dump()
    return value


def _type_hints(fn: Callable[..., Any]) -> dict[str, Any]:
    target = getattr(fn, "__func__", fn)
    try:
        return typing.get_type_hints(target)
    except Exception as exc:
        raise TypeError(
            f"Cannot resolve the annotations of {getattr(target, '__qualname__', target)}: "
            f"{exc}. Define the input and output types at module level, or pass "
            "input_type=/output_type= or input_schema=/output_schema="
        ) from exc


def derive_spec(
    fn: Callable[..., Any],
    *,
    positional: int,
    input_type: Any = None,
    output_type: Any = None,
    input_schema: dict[str, Any] | str | None = None,
    output_schema: dict[str, Any] | str | None = None,
) -> tuple[WorkflowSpec, str, str]:
    """The ``WorkflowSpec`` and the two schemas (canonical JSON; ``""`` is none) of
    ``fn``, from its annotations unless ``input_type``/``output_type`` say it.

    ``positional`` is the parameter count of the handler as the caller sees it:
    3 for an unbound ``(self, ctx, inp)`` method, 2 for ``(ctx, inp)``.
    An explicit schema wins over the one a model gives.
    """
    parameters = list(inspect.signature(fn).parameters.values())
    if len(parameters) != positional:
        shape = "(self, ctx, inp)" if positional == 3 else "(ctx, inp)"
        raise TypeError(f"A workflow handler is async def name{shape}")
    hints: dict[str, Any] = {}
    if input_type is None or output_type is None:
        hints = _type_hints(fn)
    if input_type is None:
        input_type = hints.get(parameters[-1].name, inspect.Parameter.empty)
    if output_type is None:
        output_type = hints.get("return", inspect.Parameter.empty)

    if input_type is inspect.Parameter.empty or _is_dict_type(input_type):
        in_model, in_json = None, {"type": "object"}
    elif is_model_type(input_type):
        in_model, in_json = input_type, input_type.model_json_schema()
    else:
        raise TypeError(
            "A workflow input is a pydantic model or a dict (a JSON object), "
            f"not {input_type!r}"
        )

    out_model: Any = None
    if output_type is inspect.Parameter.empty:
        out_json: dict[str, Any] | None = None
    elif output_type is None or output_type is type(None):
        out_json = {"type": "null"}
    elif is_model_type(output_type):
        out_model, out_json = output_type, output_type.model_json_schema()
    elif _is_dict_type(output_type):
        out_json = {"type": "object"}
    else:
        out_json = None  # a list, a scalar: say so with output_schema=
    return (
        WorkflowSpec(in_model, out_model),
        schema_json(
            input_schema if input_schema is not None else in_json, "input schema"
        ),
        schema_json(
            output_schema if output_schema is not None else out_json, "output schema"
        ),
    )


def validate_input(spec: WorkflowSpec, payload: dict[str, Any]) -> Any:
    """The run's payload as the handler's input; ``InvalidWorkflowInput`` when it is not."""
    if spec.input_type is None:
        return payload
    try:
        return spec.input_type.model_validate(payload)
    except Exception as exc:
        raise InvalidWorkflowInput(f"Invalid input: {str(exc)[:2000]}") from exc


def dump_output(spec: WorkflowSpec, value: Any) -> Any:
    """The handler's return value as the JSON the run record keeps."""
    if (
        spec.output_type is not None
        and _is_model_value(value)
        and not isinstance(value, spec.output_type)
    ):
        raise InvalidWorkflowOutput(
            f"A {spec.output_type.__name__} was expected, got {type(value).__name__}"
        )
    if spec.output_type is not None and not _is_model_value(value):
        if value is None or not isinstance(value, dict):
            raise InvalidWorkflowOutput(
                f"A {spec.output_type.__name__} was expected, got {type(value).__name__}"
            )
        try:
            value = spec.output_type.model_validate(value)
        except Exception as exc:
            raise InvalidWorkflowOutput(f"Invalid output: {str(exc)[:2000]}") from exc
    return _dump(value)


def workflow_handler(
    fn: Callable[..., Awaitable[Any]], spec: WorkflowSpec
) -> Callable[[JobContext], Awaitable[Any]]:
    """The job handler of ``async fn(ctx, inp)``: validates the input before ``fn``
    runs (an invalid input fails the run, without retry) and dumps its output.
    A handler that called ``ctx.skip()`` returns ``None``, whatever its output
    type: the run is SKIPPED and has no output."""

    async def handler(ctx: JobContext) -> Any:
        inp = validate_input(spec, ctx.payload)
        value = await fn(ctx, inp)
        if value is None and ctx.skipped is not None:
            return None
        return dump_output(spec, value)

    handler.__name__ = getattr(fn, "__name__", "workflow")
    handler.__qualname__ = getattr(fn, "__qualname__", handler.__name__)
    return handler


def workflow(
    name: str | None = None,
    description: str = "",
    *,
    triggers: tuple[Trigger, ...] = (),
    max_concurrency: int = 1,
    timeout: timedelta | None = None,
    max_attempts: int = 1,
    input_schema: dict[str, Any] | str | None = None,
    output_schema: dict[str, Any] | str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Declare and bind a workflow on an async module method
    ``(self, ctx: FlowContext, inp: In) -> Out``.

    ``In`` and ``Out`` are pydantic v2 models (their JSON Schemas go into the
    descriptor) or ``dict``, with ``input_schema=``/``output_schema=`` to describe
    one. ``max_attempts`` retries the whole run; finished steps are not run again.
    """

    def decorate(method: Callable[..., Any]) -> Callable[..., Any]:
        if not is_async_callable(method):
            raise TypeError(f"@workflow methods must be async: {method.__qualname__}")
        descriptor, spec = method_workflow(
            method,
            name=name,
            description=description,
            triggers=triggers,
            max_concurrency=max_concurrency,
            timeout=timeout,
            max_attempts=max_attempts,
            input_schema=input_schema,
            output_schema=output_schema,
        )
        method.__abi_job__ = descriptor  # type: ignore[attr-defined]
        method.__abi_workflow__ = spec  # type: ignore[attr-defined]
        return method

    return decorate


def method_workflow(
    method: Callable[..., Any],
    *,
    name: str | None = None,
    description: str = "",
    triggers: tuple[Trigger, ...] = (),
    max_concurrency: int = 1,
    timeout: timedelta | None = None,
    max_attempts: int = 1,
    input_schema: dict[str, Any] | str | None = None,
    output_schema: dict[str, Any] | str | None = None,
) -> tuple[JobDescriptor, WorkflowSpec]:
    """The descriptor and spec of a workflow method ``(self, ctx, inp) -> out``, as
    ``@workflow`` declares it; core's sync ``@workflow`` uses it for sync methods."""
    spec, in_schema, out_schema = derive_spec(
        method,
        positional=3,
        input_schema=input_schema,
        output_schema=output_schema,
    )
    doc = inspect.getdoc(method) or ""
    descriptor = JobDescriptor(
        name=name or method.__name__,
        description=description or (doc.splitlines()[0] if doc else ""),
        triggers=tuple(triggers),
        max_concurrency=max_concurrency,
        timeout=timeout,
        max_attempts=max_attempts,
        kind="workflow",
        input_schema=in_schema,
        output_schema=out_schema,
    )
    return descriptor, spec


def declare_workflow(
    module: Any,
    name: str,
    handler: Callable[..., Awaitable[Any]],
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
    wrap: HandlerWrap | None = None,
) -> JobDescriptor:
    """``JobsMixin.declare_workflow``. ``wrap(handler, spec)`` makes the job handler
    (default ``workflow_handler``, for an async ``handler``); core passes its own to
    run a sync handler in a worker thread."""
    if wrap is None:
        if not is_async_callable(handler):
            raise TypeError("A workflow handler must be an async callable (ctx, inp)")
        wrap = workflow_handler
    spec, in_schema, out_schema = derive_spec(
        handler,
        positional=2,
        input_type=input_type,
        output_type=output_type,
        input_schema=input_schema,
        output_schema=output_schema,
    )
    descriptor = JobDescriptor(
        name=name,
        description=description,
        triggers=tuple(triggers),
        max_concurrency=max_concurrency,
        timeout=timeout,
        max_attempts=max_attempts,
        kind="workflow",
        input_schema=in_schema,
        output_schema=out_schema,
    )
    module.declare_job(descriptor, wrap(handler, spec))
    module.__dict__.setdefault("_abi_workflow_specs", {})[name] = spec
    return descriptor


# --- the step journal ------------------------------------------------------------------


def steps_collection(project: str) -> str:
    """Step summaries, one document per (run, step key); small, listed for UIs."""
    return f"workflow_steps_{_hash(project)[:16]}"


def results_collection(project: str) -> str:
    """Step results (JSON text), read one at a time when a step is replayed."""
    return f"workflow_results_{_hash(project)[:16]}"


def step_id(run_id: str, key: str) -> str:
    # Job names have no '#': the first one splits the run id from the key.
    return f"{run_id}#{key}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def check_step_key(key: Any) -> str:
    if not isinstance(key, str) or not key:
        raise StepKeyError("A step key is a non-empty string")
    # The key is part of a message id header (a child's idempotency key): a CR or
    # LF in a key built from data would corrupt it.
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in key):
        raise StepKeyError("A step key has no control characters")
    if len(key) > MAX_STEP_KEY_LENGTH:
        raise StepKeyError(f"A step key is at most {MAX_STEP_KEY_LENGTH} characters")
    return key


def encode_result(key: str, value: Any) -> str:
    """A step result as JSON text, or ``StepResultNotJSON``/``StepResultTooLarge``."""
    try:
        encoded = json.dumps(_dump(value), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise StepResultNotJSON(
            f"Step {key!r} returned a value that is not JSON: {exc}"
        ) from exc
    size = len(encoded.encode())
    if size > MAX_STEP_RESULT_BYTES:
        raise StepResultTooLarge(
            f"Step {key!r} returned {size} bytes of JSON; a step result is at most "
            f"{MAX_STEP_RESULT_BYTES} bytes. Store large data in object storage and "
            "return a reference to it."
        )
    return encoded


MISSING: Any = object()


class StepJournal:
    """The journal of one run: a summary and a result document per step key.

    A summary written for another trigger of the same run id (a recreated jobs
    stream reuses sequence numbers) has another ``fired_at`` and counts as absent.
    Writers use CAS; a result is written before the summary that points at it, so
    a SUCCEEDED summary always has its result.
    """

    def __init__(self, documents: Any, project: str, run_id: str, fired_at: str = ""):
        self.documents, self.run_id, self.fired_at = documents, run_id, fired_at
        self.steps, self.results = (
            steps_collection(project),
            results_collection(project),
        )

    async def ensure(self) -> None:
        from naas_abi_sdk.services.models import CollectionSpec, FieldSpec

        for collection in (self.steps, self.results):
            await self.documents.ensure_collection(
                CollectionSpec(
                    name=collection,
                    fields=(FieldSpec(name="run_id", type="string", indexed=True),),
                )
            )

    def _current(self, data: dict[str, Any]) -> bool:
        return data.get("fired_at", "") == self.fired_at

    async def read(self, key: str) -> dict[str, Any]:
        """The key's summary, or ``{}`` when it has none (for this trigger)."""
        from naas_abi_sdk.services.errors import DocumentNotFound

        try:
            doc = await self.documents.get(self.steps, step_id(self.run_id, key))
        except DocumentNotFound:
            return {}
        return dict(doc.data) if self._current(doc.data) else {}

    async def _update(
        self, key: str, build: Callable[[dict[str, Any]], dict[str, Any]]
    ) -> dict[str, Any]:
        from naas_abi_sdk.services.errors import DocumentNotFound, VersionConflict

        doc_id = step_id(self.run_id, key)
        for _ in range(5):
            try:
                doc = await self.documents.get(self.steps, doc_id)
                version, prior = (
                    doc.version,
                    (dict(doc.data) if self._current(doc.data) else {}),
                )
            except DocumentNotFound:
                version, prior = 0, {}
            data = build(prior)
            try:
                await self.documents.put(self.steps, doc_id, data, if_version=version)
                return data
            except VersionConflict:
                continue
        raise VersionConflict("VERSION_CONFLICT", f"Could not journal step {key!r}")

    async def start(
        self, key: str, kind: str, *, reuse_running: bool = False
    ) -> dict[str, Any]:
        """Record a start: one more attempt (``reuse_running`` keeps the attempt of
        a start that never finished, so a child trigger repeats its idempotency key)."""

        def build(prior: dict[str, Any]) -> dict[str, Any]:
            attempt = int(prior.get("attempt") or 0)
            if not (reuse_running and prior.get("status") == "RUNNING" and attempt):
                attempt += 1
            return {
                "run_id": self.run_id,
                "key": key,
                "kind": kind,
                "status": "RUNNING",
                "attempt": attempt,
                "started_at": _now(),
                "finished_at": "",
                "duration_ms": 0,
                "error": "",
                "fired_at": self.fired_at,
                # Only a start that never journaled its child run continues: the
                # child of a FAILED (or cancelled) attempt is over, not this one's.
                **(
                    {"child": prior["child"]}
                    if reuse_running
                    and prior.get("status") == "RUNNING"
                    and "child" in prior
                    else {}
                ),
            }

        return await self._update(key, build)

    async def retry(self, key: str) -> dict[str, Any]:
        """One more attempt of a step that is running (a local retry)."""
        return await self._update(
            key, lambda p: {**p, "attempt": int(p.get("attempt") or 0) + 1, "error": ""}
        )

    async def set_child(self, key: str, child: dict[str, Any]) -> dict[str, Any]:
        return await self._update(key, lambda p: {**p, "child": child})

    async def finish(
        self,
        key: str,
        status: str,
        *,
        result: str | None = None,
        error: str = "",
        started: float | None = None,
    ) -> dict[str, Any]:
        if result is not None:
            await self.documents.put(
                self.results,
                step_id(self.run_id, key),
                {
                    "run_id": self.run_id,
                    "key": key,
                    "fired_at": self.fired_at,
                    "result_json": result,
                },
            )
        duration = (
            int((time.monotonic() - started) * 1000) if started is not None else 0
        )
        return await self._update(
            key,
            lambda p: {
                **p,
                "run_id": self.run_id,
                "key": key,
                "status": status,
                "finished_at": _now(),
                "duration_ms": duration,
                "error": error[:2000],
                "fired_at": self.fired_at,
                **(
                    {"result_bytes": len(result.encode())} if result is not None else {}
                ),
            },
        )

    async def result(self, key: str) -> Any:
        """The stored result of a SUCCEEDED step, or ``MISSING``."""
        from naas_abi_sdk.services.errors import DocumentNotFound

        try:
            doc = await self.documents.get(self.results, step_id(self.run_id, key))
        except DocumentNotFound:
            return MISSING
        if not self._current(doc.data):
            return MISSING
        return json.loads(doc.data["result_json"])

    async def summaries(self) -> list[dict[str, Any]]:
        return await read_steps(self.documents, self.steps, self.run_id)

    async def delete(self) -> None:
        await delete_steps(self.documents, self.steps, self.results, self.run_id)


_SUMMARY_FIELDS = (
    "key",
    "kind",
    "status",
    "attempt",
    "started_at",
    "finished_at",
    "duration_ms",
    "error",
    "child",
    "result_bytes",
)


async def read_steps(
    documents: Any, collection: str, run_id: str
) -> list[dict[str, Any]]:
    """A run's step summaries in the order they started: keys, status, attempt,
    timings, errors and child run references, never the results."""
    steps: list[dict[str, Any]] = []
    cursor = None
    while True:
        page = await documents.find(
            collection, where=[("run_id", "eq", run_id)], limit=1000, cursor=cursor
        )
        steps += [
            {name: doc.data[name] for name in _SUMMARY_FIELDS if name in doc.data}
            for doc in page.items
        ]
        cursor = page.cursor
        if cursor is None:
            break
    return sorted(steps, key=lambda s: (s.get("started_at", ""), s.get("key", "")))


async def delete_steps(documents: Any, steps: str, results: str, run_id: str) -> None:
    """Remove a run's journal (retention does, with the run record)."""
    from naas_abi_sdk.services.errors import DocumentNotFound, VersionConflict

    for collection in (steps, results):
        while True:
            page = await documents.find(
                collection, where=[("run_id", "eq", run_id)], limit=1000
            )
            deleted = 0
            for doc in page.items:
                try:
                    await documents.delete(collection, doc.id, if_version=doc.version)
                    deleted += 1
                except (DocumentNotFound, VersionConflict):
                    continue
            if not page.items or not deleted:
                break


# --- completion notices ----------------------------------------------------------------


class CompletionNotices:
    """Waits for runs to end: hosts publish a core-NATS notice per terminal run
    (run id and status) on the job's ``done`` subject. One subscription per job
    serves every wait on it. Core NATS is at-most-once, so each wait also reads
    the run record every ``poll_seconds``, and a notice only shortens the wait."""

    def __init__(
        self, transport: Any, *, poll_seconds: float = NOTICE_FALLBACK_POLL_SECONDS
    ):
        self.transport, self.poll_seconds = transport, poll_seconds
        self._subscriptions: dict[str, Any] = {}
        self._waiting: dict[str, dict[str, set[asyncio.Event]]] = {}
        self._lock = asyncio.Lock()

    async def _listen(self, subject: str) -> None:
        async with self._lock:
            if subject in self._subscriptions:
                return
            waiting: dict[str, set[asyncio.Event]] = {}

            async def on_notice(msg: Any) -> None:
                try:
                    run_id = json.loads(msg.data).get("run_id")
                except (ValueError, AttributeError):
                    return
                for event in waiting.get(run_id, ()):
                    event.set()

            from naas_abi_sdk.broker_flush import flush_to_broker

            nc = await self.transport.connect()
            subscription = await nc.subscribe(subject, cb=on_notice)
            await flush_to_broker(nc)
            self._waiting[subject] = waiting
            self._subscriptions[subject] = subscription

    async def wait(
        self, run: JobRun, *, timeout: float | None = None
    ) -> dict[str, Any]:
        """The run's record once it is terminal."""
        subject = job_subjects(run.project, run.module_id, run.job).done
        try:
            await self._listen(subject)
        except Exception:
            logger.warning(
                "Cannot listen for completion notices; polling", exc_info=True
            )
        event = asyncio.Event()
        waiting = self._waiting.get(subject)
        if waiting is not None:
            waiting.setdefault(run.run_id, set()).add(event)

        async def until_terminal() -> dict[str, Any]:
            while True:
                # Cleared before the read: a notice after it is not lost, and a
                # notice before it is in the record (saved first, then published).
                event.clear()
                record = await run.status()
                if record.get("status") in TERMINAL_STATUSES:
                    return record
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(event.wait(), self.poll_seconds)

        try:
            return await asyncio.wait_for(until_terminal(), timeout)
        finally:
            if waiting is not None:
                events = waiting.get(run.run_id)
                if events is not None:
                    events.discard(event)
                    if not events:
                        waiting.pop(run.run_id, None)

    async def close(self) -> None:
        subscriptions, self._subscriptions = list(self._subscriptions.values()), {}
        self._waiting.clear()
        for subscription in subscriptions:
            with contextlib.suppress(Exception):
                await subscription.unsubscribe()


# --- FlowContext -----------------------------------------------------------------------


@dataclass
class FlowRuntime:
    """What a workflow run needs of its host (``JobHost`` builds one)."""

    transport: Any
    documents: Any
    module_id: str
    project: str
    # Documents of another module's namespace, for reading its runs; None reads
    # them over the transport (what ABIClient does).
    module_documents: Callable[[str], Any] | None = None
    poll_seconds: float = NOTICE_FALLBACK_POLL_SECONDS

    def documents_for(self, module_id: str) -> Any:
        if module_id == self.module_id:
            return self.documents
        return self.module_documents(module_id) if self.module_documents else None


@dataclass
class FlowContext(JobContext):
    """A workflow run's context: ``JobContext`` plus durable steps and child runs.

    Step keys name journal entries: they must be unique within a run and the same
    on every attempt (derive them from your inputs, not from time or randomness).
    A step result is the JSON a replay would return, also on the first run.
    """

    runtime: FlowRuntime | None = field(default=None, repr=False)
    fired_at: str = ""

    def __post_init__(self) -> None:
        if self.runtime is None:
            raise ValueError("A FlowContext needs the runtime of its host")
        self._journal = StepJournal(
            self.runtime.documents, self.runtime.project, self.run_id, self.fired_at
        )
        self._notices = CompletionNotices(
            self.runtime.transport, poll_seconds=self.runtime.poll_seconds
        )
        self._used: set[str] = set()
        self._auto_calls = 0
        # Child runs not yet seen ended: cancelled with the parent.
        self._children: dict[str, JobRun] = {}

    # --- steps -----------------------------------------------------------------------

    def _claim(self, key: str) -> None:
        check_step_key(key)
        if key in self._used:
            raise StepKeyError(
                f"Step key {key!r} is used twice in run {self.run_id}: keys name "
                "journal entries and must be unique"
            )
        self._used.add(key)

    def _check_cancelled(self) -> None:
        if self.cancelled.is_set():
            raise WorkflowCancelled(f"Run {self.run_id} was cancelled")

    async def _race(self, awaitable: Awaitable[Any]) -> Any:
        """``awaitable``'s result, unless the run is cancelled first."""
        task = asyncio.ensure_future(awaitable)
        stop = asyncio.ensure_future(self.cancelled.wait())
        try:
            done, _ = await asyncio.wait(
                {task, stop}, return_when=asyncio.FIRST_COMPLETED
            )
        except asyncio.CancelledError:
            for pending in (task, stop):
                pending.cancel()
            await asyncio.gather(task, stop, return_exceptions=True)
            raise
        if task in done:
            stop.cancel()
            await asyncio.gather(stop, return_exceptions=True)
            return task.result()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        raise WorkflowCancelled(f"Run {self.run_id} was cancelled")

    @staticmethod
    async def _invoke(
        fn: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]
    ) -> Any:
        if is_async_callable(fn):
            return await fn(*args, **kwargs)
        value = await asyncio.to_thread(fn, *args, **kwargs)
        return await value if inspect.isawaitable(value) else value

    async def step(
        self,
        key: str,
        fn: Callable[..., Any],
        *args: Any,
        retries: int = 0,
        backoff: float | Callable[[int], float] = 1.0,
        **kwargs: Any,
    ) -> Any:
        """Run ``fn(*args, **kwargs)`` once for this run and journal its result.

        A step that already succeeded (an earlier attempt of the run) returns its
        stored result without calling ``fn``. ``fn`` may be sync (run in a thread)
        or async; its result must be JSON (a model is dumped), at most 256 KiB.
        ``retries`` more local attempts follow a failure, after ``backoff`` seconds
        (doubling; or ``backoff(n)`` for attempt ``n``); then the exception reaches
        the handler, and the step is recorded FAILED (it runs again on a retry of the run).
        """
        if retries < 0:
            raise ValueError("retries cannot be negative")
        self._claim(key)
        self._check_cancelled()
        journal = self._journal
        summary = await journal.read(key)
        if summary.get("status") == "SUCCEEDED":
            stored = await journal.result(key)
            if stored is not MISSING:
                return stored
        await journal.start(key, "step")
        started = time.monotonic()
        failure: Exception | None = None
        for n in range(retries + 1):
            if n:
                await journal.retry(key)
                delay = backoff(n) if callable(backoff) else backoff * 2 ** (n - 1)
            try:
                if n:  # a cancel during the backoff ends the step CANCELLED too
                    await self._race(asyncio.sleep(max(0.0, delay)))
                value = await self._race(self._invoke(fn, args, kwargs))
                encoded = encode_result(key, value)
            except WorkflowCancelled:
                await journal.finish(
                    key, "CANCELLED", error="Run cancelled", started=started
                )
                raise
            except NonRetryable as exc:
                await journal.finish(
                    key, "FAILED", error=_describe(exc), started=started
                )
                raise
            except Exception as exc:
                failure = exc
                logger.warning(
                    "Step %r of run %s failed (attempt %d)",
                    key,
                    self.run_id,
                    n + 1,
                    exc_info=True,
                )
                continue
            await journal.finish(key, "SUCCEEDED", result=encoded, started=started)
            return json.loads(encoded)
        assert failure is not None
        await journal.finish(key, "FAILED", error=_describe(failure), started=started)
        raise failure

    async def _fan_out(
        self,
        key: str,
        items: Iterable[Any],
        one: Callable[[Any, int], Awaitable[Any]],
        concurrency: int,
    ) -> list[Any]:
        if concurrency < 1:
            raise ValueError("concurrency must be at least 1")
        self._claim(key)
        items = list(items)
        if len(items) > MAX_FAN_OUT:
            raise ValueError(
                f"{key!r} fans out over {len(items)} items; at most {MAX_FAN_OUT}. "
                "Split them into batches, one child workflow per batch."
            )
        slots = asyncio.Semaphore(concurrency)

        async def guarded(index: int, item: Any) -> Any:
            async with slots:
                return await one(item, index)

        tasks = [
            asyncio.ensure_future(guarded(i, item)) for i, item in enumerate(items)
        ]
        try:
            _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
        except asyncio.CancelledError:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
        for (
            task
        ) in pending:  # one failed: the rest stop, journaled work stays journaled
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        failure: BaseException | None = None
        for task in tasks:  # every exception is read, so none is left unretrieved
            if (
                not task.cancelled()
                and task.exception() is not None
                and failure is None
            ):
                failure = task.exception()
        if failure is not None:
            raise failure
        return [task.result() for task in tasks]

    async def map(
        self,
        key: str,
        items: Iterable[Any],
        fn: Callable[..., Any],
        *,
        concurrency: int = DEFAULT_FAN_OUT_CONCURRENCY,
    ) -> list[Any]:
        """``step`` over each item in this process, ``concurrency`` at a time; item
        ``i`` is journaled as ``key[i]``, so the items must come in the same order
        on every attempt (take them from an earlier step). Results keep that order."""
        return await self._fan_out(
            key, items, lambda item, i: self.step(f"{key}[{i}]", fn, item), concurrency
        )

    # --- child runs ------------------------------------------------------------------

    def _child_run(self, child: dict[str, Any]) -> JobRun:
        rt = self.runtime
        assert rt is not None
        return JobRun(
            rt.transport,
            rt.project,
            child["module_id"],
            child["workflow"],
            child["run_id"],
            rt.documents_for(child["module_id"]),
        )

    def _refuse_self(self, module_id: str, workflow: str) -> None:
        assert self.runtime is not None
        if module_id == self.runtime.module_id and workflow == self.job:
            raise SelfCall(
                f"Workflow {workflow!r} of module {module_id!r} cannot call itself: its "
                "child would wait for the slot its parent holds. Split the work into "
                "another workflow."
            )

    async def _await_run(self, run: JobRun) -> dict[str, Any]:
        return await self._race(self._notices.wait(run))

    async def _call(self, key: str, module_id: str, workflow: str, input: Any) -> Any:
        rt = self.runtime
        assert rt is not None
        self._refuse_self(module_id, workflow)
        self._claim(key)
        self._check_cancelled()
        payload = encode_input(input)
        journal = self._journal
        summary = await journal.read(key)
        if summary.get("status") == "SUCCEEDED":
            stored = await journal.result(key)
            if stored is not MISSING:
                return stored
        child = summary.get("child") if summary.get("status") == "RUNNING" else None
        started = time.monotonic()
        if child:
            # A replay: the child was triggered before. Wait for that run.
            run = self._child_run(child)
        else:
            started_step = await journal.start(key, "call", reuse_running=True)
            proxy = JobProxy(
                rt.transport,
                rt.project,
                module_id,
                JobDescriptor(workflow, kind="workflow"),
                rt.documents_for(module_id),
            )
            # The run id and step attempt make the trigger one message inside the
            # stream's duplicate window, should this host die before it journals the child.
            run = await proxy.trigger(
                payload,
                idempotency_key=f"{self.run_id}/{key}/{started_step['attempt']}",
            )
            child = {"module_id": module_id, "workflow": workflow, "run_id": run.run_id}
            await journal.set_child(key, child)
        self._children[key] = run
        record = await self._await_run(run)
        self._children.pop(key, None)
        status = record.get("status")
        if status not in ("SUCCEEDED", "SKIPPED"):  # a skipped child's output is None
            error = (
                f"Child run {run.run_id} of {module_id}.{workflow} ended {status}: "
                f"{record.get('error') or 'no error recorded'}"
            )
            await journal.finish(key, "FAILED", error=error, started=started)
            raise ChildRunFailed(error)
        output = record.get("result")
        if (
            isinstance(output, dict)
            and set(output) == _TRUNCATED
            and output["truncated"] is True
        ):
            message = (
                f"Child run {run.run_id} of {module_id}.{workflow} returned more than "
                "the host keeps of a result; return a reference to object storage instead"
            )
            await journal.finish(key, "FAILED", error=message, started=started)
            raise ChildOutputTruncated(message)
        try:
            encoded = encode_result(key, output)
        except NonRetryable as exc:
            await journal.finish(key, "FAILED", error=_describe(exc), started=started)
            raise
        await journal.finish(key, "SUCCEEDED", result=encoded, started=started)
        return json.loads(encoded)

    async def call(
        self, module_id: str, workflow: str, input: Any = None, key: str | None = None
    ) -> Any:
        """Run another module's workflow as a child run and return its output.

        The child's run id is journaled before waiting: a replay waits for that
        run instead of starting another. The step key defaults to a counter over
        the calls made without one; pass ``key`` where calls are conditional.
        A workflow cannot call itself (``SelfCall``); the parent keeps its slot
        and its heartbeats while it waits, and cancelling it cancels the child.
        """
        if key is None:
            self._auto_calls += 1
            key = f"call:{module_id}.{workflow}#{self._auto_calls}"
        return await self._call(key, module_id, workflow, input)

    async def map_call(
        self,
        key: str,
        module_id: str,
        workflow: str,
        inputs: Iterable[Any],
        *,
        concurrency: int = DEFAULT_FAN_OUT_CONCURRENCY,
    ) -> list[Any]:
        """``call`` once per input, ``concurrency`` children at a time, each on
        whichever replica takes it; child ``i`` is journaled as ``key[i]``.
        Outputs keep the order of ``inputs``."""
        self._refuse_self(module_id, workflow)
        return await self._fan_out(
            key,
            inputs,
            lambda item, i: self._call(f"{key}[{i}]", module_id, workflow, item),
            concurrency,
        )

    async def steps(self) -> list[dict[str, Any]]:
        """This run's step summaries (see ``WorkflowRun.steps``)."""
        return await self._journal.summaries()

    # --- the host's side -------------------------------------------------------------

    async def finish(self, status: str) -> None:
        """Called by the host once the handler ended with ``status``, the run's
        final one (``RETRYING`` when another attempt follows). A run that ends for
        good without its output (cancelled, timed out, failed) cancels the children
        it still waited for, so they free their slots; a run that will be retried
        leaves them running, and its next attempt re-attaches to them."""
        if status not in STOPPED_PARENT_STATUSES:
            return
        error = (
            "The parent run was cancelled"
            if status == "CANCELLED"
            else f"The parent run ended {status}"
        )
        for key, run in list(self._children.items()):
            try:
                await run.cancel()
                await self._journal.finish(key, "CANCELLED", error=error)
            except Exception:
                logger.warning(
                    "Could not cancel child run %s", run.run_id, exc_info=True
                )
        self._children.clear()

    async def close(self) -> None:
        """Release what the run holds (the host calls it as the run ends)."""
        await self._notices.close()


def _describe(error: BaseException) -> str:
    return f"{type(error).__name__}: {error}"[:2000]


def encode_input(value: Any, input_type: Any = None) -> dict[str, Any]:
    """A workflow input as the JSON object a trigger carries: a dict, or a model
    (checked against ``input_type`` when that is given)."""
    if (
        input_type is not None
        and is_model_type(input_type)
        and (isinstance(value, dict) or value is None)
    ):
        value = input_type.model_validate(value or {})
    value = _dump(value)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError("A workflow input is a dict or a model (a JSON object)")
    return value


# --- the caller side -------------------------------------------------------------------


async def _on_loop(
    loop: asyncio.AbstractEventLoop | None, make: Callable[[], Awaitable[Any]]
) -> Any:
    """Run ``make()`` on ``loop`` (the host's), whichever loop awaits this."""
    if loop is None:
        return await make()
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None
    if running is loop:
        return await make()
    return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(make(), loop))


class WorkflowRun:
    """A started workflow run: its record, its steps, its output, a cancel."""

    def __init__(
        self,
        run: JobRun,
        *,
        output_type: Any = None,
        loop: asyncio.AbstractEventLoop | None = None,
        poll_seconds: float = NOTICE_FALLBACK_POLL_SECONDS,
    ):
        self._run, self.output_type, self._loop = run, output_type, loop
        self.poll_seconds = poll_seconds

    @property
    def run_id(self) -> str:
        return self._run.run_id

    @property
    def module_id(self) -> str:
        return self._run.module_id

    @property
    def workflow(self) -> str:
        return self._run.job

    @property
    def duplicate(self) -> bool:
        """The start repeated an idempotency key inside the duplicate window: this is
        the first start's run."""
        return self._run.duplicate

    async def status(self) -> dict[str, Any]:
        """The run record (``{"status": "QUEUED"}`` until a host takes the run)."""
        return await _on_loop(self._loop, self._run.status)

    async def wait(self, *, timeout: float | None = None) -> dict[str, Any]:
        """The run record once the run is terminal. Woken by its host's completion
        notice, with a slow poll as the fallback."""

        async def wait() -> dict[str, Any]:
            notices = CompletionNotices(
                self._run.transport, poll_seconds=self.poll_seconds
            )
            try:
                return await notices.wait(self._run, timeout=timeout)
            finally:
                await notices.close()

        return await _on_loop(self._loop, wait)

    async def result(self, *, timeout: float | None = None) -> Any:
        """The output (a model when ``output_type`` says so) once the run
        succeeded; ``None`` for a run that skipped (``ctx.skip()``: nothing to do,
        so no output); ``WorkflowRunFailed`` if it ended any other way."""
        record = await self.wait(timeout=timeout)
        if record.get("status") not in ("SUCCEEDED", "SKIPPED"):
            raise WorkflowRunFailed(
                self.run_id, str(record.get("status")), str(record.get("error") or "")
            )
        if record.get("status") == "SKIPPED":
            return None
        output = record.get("result")
        if (
            isinstance(output, dict)
            and set(output) == _TRUNCATED
            and output["truncated"] is True
        ):
            raise WorkflowRunFailed(
                self.run_id,
                "SUCCEEDED",
                "its output went over what a run record keeps; return a reference "
                "to object storage instead",
            )
        if self.output_type is not None and is_model_type(self.output_type):
            return self.output_type.model_validate(output)
        return output

    async def steps(self) -> list[dict[str, Any]]:
        """The step summaries in start order: ``key``, ``kind`` (``step`` or
        ``call``), ``status``, ``attempt``, ``started_at``, ``finished_at``,
        ``duration_ms``, ``error``, ``child`` (``module_id``, ``workflow``,
        ``run_id`` of a child run) and ``result_bytes``. Results are not loaded."""

        async def read() -> list[dict[str, Any]]:
            return await read_steps(
                self._run._docs(), steps_collection(self._run.project), self.run_id
            )

        return await _on_loop(self._loop, read)

    async def cancel(self) -> None:
        """Cooperative: the host sets ``ctx.cancelled``, and the run cancels its
        running children."""
        await _on_loop(self._loop, self._run.cancel)


class WorkflowProxy:
    """A workflow of a module: ``start`` it, or ``run`` it for its output."""

    def __init__(
        self,
        transport: Any,
        project: str,
        module_id: str,
        descriptor: JobDescriptor,
        documents: Any = None,
        *,
        input_type: Any = None,
        output_type: Any = None,
        loop: asyncio.AbstractEventLoop | None = None,
        poll_seconds: float = NOTICE_FALLBACK_POLL_SECONDS,
    ):
        self.transport, self.project, self.module_id = transport, project, module_id
        self.descriptor, self._documents = descriptor, documents
        self.input_type, self.output_type = input_type, output_type
        self._loop, self.poll_seconds = loop, poll_seconds

    @property
    def name(self) -> str:
        return self.descriptor.name

    @property
    def input_schema(self) -> dict[str, Any] | None:
        return (
            json.loads(self.descriptor.input_schema)
            if self.descriptor.input_schema
            else None
        )

    @property
    def output_schema(self) -> dict[str, Any] | None:
        return (
            json.loads(self.descriptor.output_schema)
            if self.descriptor.output_schema
            else None
        )

    async def start(
        self, input: Any = None, *, idempotency_key: str | None = None
    ) -> WorkflowRun:
        """Store a trigger carrying ``input`` (a dict or a model); the run starts
        when a host takes it. A repeated ``idempotency_key`` inside the stream's
        duplicate window (2 minutes) is the same run."""
        payload = encode_input(input, self.input_type)

        async def trigger() -> JobRun:
            return await JobProxy(
                self.transport,
                self.project,
                self.module_id,
                self.descriptor,
                self._documents,
            ).trigger(payload, idempotency_key=idempotency_key)

        return WorkflowRun(
            await _on_loop(self._loop, trigger),
            output_type=self.output_type,
            loop=self._loop,
            poll_seconds=self.poll_seconds,
        )

    async def run(self, input: Any = None, *, timeout: float | None = None) -> Any:
        """``start``, wait, and return the output; ``timeout`` bounds the wait
        (``asyncio.TimeoutError``; the run goes on)."""
        return await (await self.start(input)).result(timeout=timeout)

    def as_tools(self) -> list[Any]:
        """One LangChain tool that runs this workflow and returns its output (as
        JSON): named after it (``workflow.greet_workflow`` is ``greet_workflow``),
        described by its descriptor, its arguments the input schema. Create it
        inside the running module, as ``agent_tools`` does: a sync call runs on
        the loop the tool was created on. Needs ``naas-abi-sdk[agents]``."""
        try:
            from langchain_core.tools import StructuredTool
        except ImportError as exc:
            raise ImportError(
                "WorkflowProxy.as_tools needs LangChain: pip install 'naas-abi-sdk[agents]'"
            ) from exc
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        async def call(**arguments: Any) -> Any:
            return _dump(await self.run(arguments))

        def call_from_thread(**arguments: Any) -> Any:
            if loop is None or not loop.is_running():
                raise RuntimeError(
                    "Create workflow tools inside the running module; use ainvoke "
                    "for async callers"
                )
            try:
                current = asyncio.get_running_loop()
            except RuntimeError:
                current = None
            if current is loop:
                raise RuntimeError("Use tool.ainvoke on the module event loop")
            return asyncio.run_coroutine_threadsafe(call(**arguments), loop).result()

        name = re.sub(r"[^A-Za-z0-9_-]", "_", self.name.rsplit(".", 1)[-1])[:64]
        return [
            StructuredTool.from_function(
                func=call_from_thread,
                coroutine=call,
                name=name,
                description=self.descriptor.description or self.name,
                args_schema=self.input_schema or {"type": "object", "properties": {}},
            )
        ]


def host_workflow(
    host: Any, loop: asyncio.AbstractEventLoop, name: str, spec: WorkflowSpec
) -> WorkflowProxy:
    """A module's own workflow, through its bound host (``JobsMixin.get_workflow``)."""
    if name not in host.handlers:
        raise ValueError(f"Module {host.module_id} has no workflow named {name!r}")
    return WorkflowProxy(
        host.transport,
        host.project,
        host.module_id,
        host.handlers[name][0],
        host.documents,
        input_type=spec.input_type,
        output_type=spec.output_type,
        loop=loop,
        poll_seconds=host.workflow_poll_seconds,
    )
