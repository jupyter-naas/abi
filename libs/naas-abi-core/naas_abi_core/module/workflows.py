"""Durable workflows for engine modules: the SDK's ``@workflow`` and ``FlowContext``,
plus sync handlers.

A workflow is a job with a typed input and output whose handler checkpoints its
steps (``naas_abi_sdk.workflows``, docs/adr/20261025_durable-workflows-on-nats.md).
Engine modules write them like SDK modules, with async handlers that use the
SDK's ``FlowContext`` as is, or with sync handlers, which the engine runs in a
worker thread (``SyncJobRunner``) and hands a ``SyncFlowContext``::

    class ABIModule(BaseModule):
        @workflow(max_attempts=3)
        def report(self, ctx: SyncFlowContext, inp: ReportInput) -> ReportOutput:
            rows = ctx.step("load", self.load, inp.table)
            ctx.map_call("push", "acme.sink", "push", [{"row": r} for r in rows])
            return ReportOutput(count=len(rows))

Without ``naas-abi-sdk`` (core installed without ``[nats]``), inert stand-ins keep
modules importable; workflows need NATS mode to run anyway.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextvars
import inspect
import queue
from collections.abc import Awaitable, Callable, Iterable
from datetime import timedelta
from typing import Any

try:
    from naas_abi_sdk.jobs import JobDescriptor, Trigger, is_async_callable
    from naas_abi_sdk.workflows import (
        DEFAULT_FAN_OUT_CONCURRENCY,
        MAX_FAN_OUT,
        ChildRunFailed,
        FlowContext,
        InvalidWorkflowInput,
        InvalidWorkflowOutput,
        SelfCall,
        StepKeyError,
        StepResultTooLarge,
        WorkflowCancelled,
        WorkflowError,
        WorkflowProxy,
        WorkflowRun,
        WorkflowRunFailed,
        derive_spec,
        dump_output,
        validate_input,
    )
    from naas_abi_sdk.workflows import workflow as _sdk_workflow

    WORKFLOWS_AVAILABLE = True
except ImportError:  # core without [nats]
    from naas_abi_core.module.workflows_fallback import (  # type: ignore[assignment]
        WORKFLOWS_AVAILABLE,
        ChildRunFailed,
        FlowContext,
        InvalidWorkflowInput,
        InvalidWorkflowOutput,
        SelfCall,
        StepKeyError,
        StepResultTooLarge,
        WorkflowCancelled,
        WorkflowError,
        WorkflowProxy,
        WorkflowRun,
        WorkflowRunFailed,
        workflow,
    )

    DEFAULT_FAN_OUT_CONCURRENCY = 8
    MAX_FAN_OUT = 10_000
    is_async_callable = inspect.iscoroutinefunction  # type: ignore[assignment]

# How often a blocked worker thread looks at its run again: a blocking wait with no
# timeout would hold off ``JobInterrupted`` until it returned.
POLL_SECONDS = 0.2


class SyncFlowContext:
    """The context of a sync workflow handler: ``FlowContext``, with blocking calls.

    ``step``, ``map``, ``call``, ``map_call`` and ``steps`` take the arguments of
    ``FlowContext`` and block the worker thread, while the journal and the child
    runs are handled on the job host's loop. Everything else (``payload``,
    ``run_id``, ``attempt``, ``cancelled``, ``log``, ``skip``...) is the
    ``FlowContext``'s.

    A ``step`` function runs in the handler's own thread, so the run's
    ``JobInterrupted`` grace behaviour reaches it, and a run that timed out keeps
    its concurrency slot until the function returns. ``map`` runs its items on
    ``concurrency`` worker threads of its own: ``JobInterrupted`` does not reach
    them, so item functions of a long ``map`` should look at ``ctx.cancelled``.
    ``ctx.cancelled`` is an ``asyncio.Event``: use ``is_set()``.
    """

    def __init__(self, ctx: Any, loop: asyncio.AbstractEventLoop):
        self._ctx, self._loop = ctx, loop

    def __getattr__(self, name: str) -> Any:
        return getattr(self._ctx, name)

    # --- running a coroutine on the host's loop, from this thread ---------------------

    def _submit(self, coro: Awaitable[Any]) -> concurrent.futures.Future[Any]:
        """Schedule ``coro`` on the host's loop, in this thread's context copy (so
        its service calls nest under the run's trace span, as ``SyncJobRunner``'s do)."""
        future: concurrent.futures.Future[Any] = concurrent.futures.Future()
        context = contextvars.copy_context()

        def start() -> None:
            task: asyncio.Task[Any] = self._loop.create_task(coro)  # type: ignore[arg-type]

            def finished(done: asyncio.Task[Any]) -> None:
                # The waiting thread may have cancelled the future already (an
                # interrupt), and the task finished before its cancel arrived.
                if future.cancelled():
                    return
                try:
                    if done.cancelled():
                        future.cancel()
                    elif done.exception() is not None:
                        future.set_exception(done.exception())  # type: ignore[arg-type]
                    else:
                        future.set_result(done.result())
                except concurrent.futures.InvalidStateError:
                    pass  # cancelled between the check and the set

            task.add_done_callback(finished)
            # A cancel from this thread (an interrupt while it waits) reaches the task.
            future.add_done_callback(
                lambda f: f.cancelled() and self._loop.call_soon_threadsafe(task.cancel)
            )

        self._loop.call_soon_threadsafe(start, context=context)
        return future

    def _drive(
        self, coro: Awaitable[Any], requests: queue.Queue[Any] | None = None
    ) -> Any:
        """Wait for ``coro`` (run on the host's loop). ``requests`` carries work for
        this thread to do meanwhile (a step function)."""
        inbox: queue.Queue[Any] = requests if requests is not None else queue.Queue()
        future = self._submit(coro)
        future.add_done_callback(lambda _f: inbox.put(None))
        try:
            while True:
                try:
                    work = inbox.get(timeout=POLL_SECONDS)
                except queue.Empty:
                    work = None
                if work is not None:
                    work()
                elif future.done():
                    break
            return future.result()
        except BaseException:
            future.cancel()
            raise

    # --- FlowContext, blocking --------------------------------------------------------

    def step(
        self,
        key: str,
        fn: Callable[..., Any],
        *args: Any,
        retries: int = 0,
        backoff: float | Callable[[int], float] = 1.0,
        **kwargs: Any,
    ) -> Any:
        """``FlowContext.step``, with ``fn`` run in this thread (a sync function)."""
        if is_async_callable(fn):
            return self._drive(
                self._ctx.step(
                    key, fn, *args, retries=retries, backoff=backoff, **kwargs
                )
            )
        requests: queue.Queue[Any] = queue.Queue()
        interrupted: list[BaseException] = []

        async def in_this_thread() -> Any:
            outcome = self._loop.create_future()

            def settle(error: BaseException | None, value: Any = None) -> None:
                if outcome.done():
                    return
                if error is None:
                    outcome.set_result(value)
                elif isinstance(error, Exception):
                    outcome.set_exception(error)
                else:  # JobInterrupted: the run is being stopped, not the step failing
                    outcome.cancel()

            def execute() -> None:
                try:
                    value = fn(*args, **kwargs)
                except BaseException as exc:  # noqa: BLE001 - handed to the step
                    if not isinstance(exc, Exception):
                        interrupted.append(exc)
                    self._loop.call_soon_threadsafe(settle, exc)
                else:
                    self._loop.call_soon_threadsafe(settle, None, value)

            requests.put(execute)
            return await outcome

        try:
            return self._drive(
                self._ctx.step(key, in_this_thread, retries=retries, backoff=backoff),
                requests,
            )
        except BaseException:
            if interrupted:
                raise interrupted[0] from None
            raise

    def map(
        self,
        key: str,
        items: Iterable[Any],
        fn: Callable[..., Any],
        *,
        concurrency: int = DEFAULT_FAN_OUT_CONCURRENCY,
    ) -> list[Any]:
        """``FlowContext.map``: item ``i`` is the step ``key[i]``, ``concurrency`` at a
        time on worker threads of this call. The first failure stops the items not
        started yet; the running ones finish."""
        if concurrency < 1:
            raise ValueError("concurrency must be at least 1")
        self._ctx._claim(key)  # a map's key is unique within the run, like a step's
        items = list(items)
        if len(items) > MAX_FAN_OUT:
            raise ValueError(
                f"{key!r} fans out over {len(items)} items; at most {MAX_FAN_OUT}. "
                "Split them into batches, one child workflow per batch."
            )
        failure: BaseException | None = None
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=max(1, min(concurrency, len(items))),
            thread_name_prefix=f"abi-map-{self._ctx.run_id}",
        ) as pool:
            futures = [
                pool.submit(
                    contextvars.copy_context().run,
                    self.step,
                    f"{key}[{i}]",
                    fn,
                    item,
                )
                for i, item in enumerate(items)
            ]
            pending = set(futures)
            try:
                while pending:
                    done, pending = concurrent.futures.wait(
                        pending,
                        timeout=POLL_SECONDS,
                        return_when=concurrent.futures.FIRST_COMPLETED,
                    )
                    for finished in done:
                        if finished.cancelled():
                            continue
                        if failure is None and finished.exception() is not None:
                            failure = finished.exception()
                            for waiting in pending:
                                waiting.cancel()
            finally:  # the pool joins its workers on the way out
                for waiting in pending:
                    waiting.cancel()
        if failure is not None:
            raise failure
        return [f.result() for f in futures]

    def call(
        self, module_id: str, workflow: str, input: Any = None, key: str | None = None
    ) -> Any:
        """``FlowContext.call``: start a child run of another module's workflow, wait
        for its output."""
        return self._drive(self._ctx.call(module_id, workflow, input, key=key))

    def map_call(
        self,
        key: str,
        module_id: str,
        workflow: str,
        inputs: Iterable[Any],
        *,
        concurrency: int = DEFAULT_FAN_OUT_CONCURRENCY,
    ) -> list[Any]:
        """``FlowContext.map_call``: one child run per input, ``concurrency`` at a time."""
        return self._drive(
            self._ctx.map_call(
                key, module_id, workflow, inputs, concurrency=concurrency
            )
        )

    def steps(self) -> list[dict[str, Any]]:
        """``FlowContext.steps``: this run's step summaries."""
        return self._drive(self._ctx.steps())


def sync_workflow_handler(
    fn: Callable[..., Any], spec: Any
) -> Callable[[SyncFlowContext], Any]:
    """The job handler of a sync ``fn(ctx, inp)``: what ``workflow_handler`` is to an
    async one. The engine runs it in a worker thread with a ``SyncFlowContext``."""

    def handler(ctx: SyncFlowContext) -> Any:
        inp = validate_input(spec, ctx.payload)
        value = fn(ctx, inp)
        if value is None and ctx.skipped is not None:
            return None
        return dump_output(spec, value)

    handler.__name__ = getattr(fn, "__name__", "workflow")
    handler.__qualname__ = getattr(fn, "__qualname__", handler.__name__)
    handler.__abi_sync_flow__ = True  # type: ignore[attr-defined]
    return handler


if WORKFLOWS_AVAILABLE:

    def workflow(  # type: ignore[no-redef,misc]
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
        """Declare and bind a workflow on a module method ``(self, ctx, inp) -> Out``.

        Async methods are the SDK's (``ctx`` is a ``FlowContext``). A sync method
        runs in a worker thread and gets a ``SyncFlowContext``, whose ``step``,
        ``map``, ``call`` and ``map_call`` block. ``In`` and ``Out`` are pydantic
        models or ``dict`` (see ``naas_abi_sdk.workflows.workflow``).
        """
        decorate_async = _sdk_workflow(
            name,
            description,
            triggers=triggers,
            max_concurrency=max_concurrency,
            timeout=timeout,
            max_attempts=max_attempts,
            input_schema=input_schema,
            output_schema=output_schema,
        )

        def decorate(method: Callable[..., Any]) -> Callable[..., Any]:
            if is_async_callable(method):
                return decorate_async(method)
            spec, in_schema, out_schema = derive_spec(
                method,
                positional=3,
                input_schema=input_schema,
                output_schema=output_schema,
            )
            doc = inspect.getdoc(method) or ""
            # The descriptor of naas_abi_sdk.workflows.workflow, for a sync method: keep
            # the two in step.
            method.__abi_job__ = JobDescriptor(  # type: ignore[attr-defined]
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
            # Not __abi_workflow__: the SDK mixin would wrap it as an async handler.
            method.__abi_sync_workflow__ = spec  # type: ignore[attr-defined]
            return method

        return decorate


__all__ = [
    "WORKFLOWS_AVAILABLE",
    "ChildRunFailed",
    "FlowContext",
    "InvalidWorkflowInput",
    "InvalidWorkflowOutput",
    "SelfCall",
    "StepKeyError",
    "StepResultTooLarge",
    "SyncFlowContext",
    "WorkflowCancelled",
    "WorkflowError",
    "WorkflowProxy",
    "WorkflowRun",
    "WorkflowRunFailed",
    "sync_workflow_handler",
    "workflow",
]
