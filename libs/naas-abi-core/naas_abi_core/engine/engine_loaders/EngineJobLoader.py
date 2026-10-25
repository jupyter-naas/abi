"""Host the jobs of engine modules in this process (NATS mode only).

Engine modules declare jobs exactly like SDK modules (``naas_abi_core.module.jobs``),
and workflows too (``naas_abi_core.module.workflows``, including the ones the
Workflow/Pipeline bridge declares). Each module with jobs gets one SDK ``JobHost``:
same stream, subjects, consumers and run records as a standalone module, so
callers cannot tell them apart.

Hosts run on a dedicated event loop thread, never on ``nats_runtime``'s loop:
a slow job must not stall the engine's NATS service endpoints. Sync handlers
run in their own thread, where blocking engine service calls are safe, and are
interrupted on timeout or cancel (``SyncJobRunner``).
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from collections.abc import Callable, Mapping
from typing import Any

from naas_abi_core import logger
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    NATSConfiguration,
)
from naas_abi_core.engine.engine_loaders.SyncJobRunner import SyncJobRunner

ENGINE_IDENTITY = "engine"
LOOP_THREAD_NAME = "abi-engine-jobs-loop"
START_TIMEOUT_SECONDS = 60.0


def as_async_handler(
    handler: Callable[..., Any], *, interrupt_grace_seconds: float | None = 5.0
) -> Callable[..., Any]:
    """Async handlers are used as is; sync ones run in their own thread and are
    interrupted on timeout or cancel (see ``SyncJobRunner``). A sync workflow gets a
    ``SyncFlowContext`` whose steps block on the host's loop."""
    from naas_abi_sdk.jobs import is_async_callable

    if is_async_callable(handler):
        return handler
    context_factory = None
    if getattr(handler, "__abi_sync_flow__", False):
        from naas_abi_core.module.workflows import SyncFlowContext

        context_factory = SyncFlowContext
    return SyncJobRunner(
        handler,
        interrupt_grace_seconds=interrupt_grace_seconds,
        context_factory=context_factory,
    )


class LoopThread:
    """An event loop on its own daemon thread, for engine work that must not
    wait behind ``nats_runtime``'s loop."""

    def __init__(self, name: str = LOOP_THREAD_NAME) -> None:
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(
            target=self.loop.run_forever, daemon=True, name=name
        )
        self.thread.start()

    def run(self, coro: Any, timeout: float) -> Any:
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)

    def stop(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=5.0)
        if not self.thread.is_alive():
            self.loop.close()


def _is_workflow(descriptor: Any) -> bool:
    return getattr(descriptor, "kind", "job") == "workflow"


def _default_documents(transport: Any, module_id: str) -> Any:
    from naas_abi_sdk.document import DocumentClient
    from naas_abi_sdk.services.document import DocumentService

    return DocumentService(DocumentClient(transport).for_namespace(module_id))


def _default_host(*args: Any, **kwargs: Any) -> Any:
    from naas_abi_sdk.job_host import JobHost

    return JobHost(*args, **kwargs)


class EngineJobLoader:
    def __init__(
        self,
        configuration: NATSConfiguration | None,
        *,
        documents_factory: Callable[[Any, str], Any] = _default_documents,
        host_factory: Callable[..., Any] = _default_host,
        host_options: Mapping[str, Any] | None = None,
    ) -> None:
        self.configuration = configuration
        self.documents_factory = documents_factory
        self.host_factory = host_factory
        self.host_options = dict(host_options or {})
        self.hosts: list[Any] = []
        # Modules bound to their host, for their own triggers (trigger_job).
        self._bound: list[Any] = []
        self._loop: LoopThread | None = None
        self._transport: Any = None
        # Documents of each module's namespace, shared by the hosts that read
        # the runs of other modules (a workflow's children).
        self._documents: dict[str, Any] = {}

    @property
    def project(self) -> str:
        discovery = self.configuration.discovery if self.configuration else None
        return discovery.project if discovery is not None else "default"

    def start(self, modules: Mapping[str, Any], *, document_available: bool) -> None:
        """Start a host per module with jobs. Raises if a declared job cannot run."""
        with_jobs = {mid: m for mid, m in modules.items() if getattr(m, "jobs", ())}
        if not with_jobs:
            return
        if self.configuration is None:
            logger.warning(
                "Engine jobs and workflows need NATS mode; not hosting those of "
                f"{sorted(with_jobs)}"
            )
            return
        if not self.configuration.jobs.enabled:
            logger.info(
                "Engine jobs disabled; not hosting the jobs and workflows of "
                f"{sorted(with_jobs)}"
            )
            return
        for module_id, module in with_jobs.items():
            missing = module.missing_job_handlers()
            if missing:
                raise ValueError(
                    f"Module {module_id} declares jobs without handlers: {sorted(missing)}"
                )
        if not document_available:
            raise ValueError(
                "Engine jobs need the document service for their run records"
            )

        self._ensure_loop()
        try:
            for module_id, module in with_jobs.items():
                self._start_host(module_id, module)
        except BaseException:
            self.stop()
            raise
        workflows = sum(
            1 for m in with_jobs.values() for j in m.jobs if _is_workflow(j)
        )
        logger.info(
            f"Engine jobs: hosting {sum(len(m.jobs) for m in with_jobs.values())} job(s) "
            f"({workflows} workflow(s)) of {sorted(with_jobs)} in project {self.project!r}"
        )

    def _ensure_loop(self) -> LoopThread:
        if self._loop is None:
            self._loop = LoopThread()
        return self._loop

    def _ensure_transport(self) -> Any:
        assert self.configuration is not None
        if self._transport is None:
            from naas_abi_core.engine.nats_auth import ServiceTokenSource
            from naas_abi_core.engine.nats_naming import connection_name
            from naas_abi_sdk.transport import Transport

            secret = self.configuration.jwt_secret
            self._transport = Transport(
                self.configuration.nats_url,
                ServiceTokenSource(ENGINE_IDENTITY, secret),
                name=connection_name("abi-engine:jobs"),
            )
        return self._transport

    def module_documents(self, module_id: str) -> Any:
        """The documents of ``module_id``'s namespace: where its run records and
        journals are, for a workflow reading the runs of its children."""
        documents = self._documents.get(module_id)
        if documents is None:
            documents = self.documents_factory(self._ensure_transport(), module_id)
            self._documents[module_id] = documents
        return documents

    def workflow(
        self,
        module_id: str,
        name: str,
        *,
        input_type: Any = None,
        output_type: Any = None,
    ) -> Any:
        """A ``WorkflowProxy`` for the workflow ``name`` of any module (engine or
        remote), on this engine's connection: ``start(input)`` or ``run(input)``.
        Its methods are awaitable from any loop. Nothing is checked until a start:
        an unknown workflow's runs stay QUEUED."""
        from naas_abi_core.module.jobs import JobsNotHosted

        if self.configuration is None:
            raise JobsNotHosted("Workflows run in NATS mode")
        from naas_abi_sdk.jobs import JobDescriptor
        from naas_abi_sdk.workflows import WorkflowProxy

        loop = self._ensure_loop()
        return WorkflowProxy(
            self._ensure_transport(),
            self.project,
            module_id,
            JobDescriptor(name, kind="workflow"),
            self.module_documents(module_id),
            input_type=input_type,
            output_type=output_type,
            loop=loop.loop,
        )

    def _start_host(self, module_id: str, module: Any) -> None:
        assert self._loop is not None and self.configuration is not None
        transport = self._ensure_transport()
        handlers = module._job_handlers
        host = self.host_factory(
            transport,
            self.module_documents(module_id),
            module_id,
            self.project,
            {
                j.name: (
                    j,
                    as_async_handler(
                        handlers[j.name],
                        interrupt_grace_seconds=self.configuration.jobs.interrupt_grace_seconds,
                    ),
                )
                for j in module.jobs
            },
            instance_id=f"engine-{uuid.uuid4().hex[:12]}",
            module_documents=self.module_documents,
            **{
                "retention": self.configuration.jobs.retention.to_retention(),
                **self.host_options,
            },
        )
        self._loop.run(host.start(), START_TIMEOUT_SECONDS)
        self.hosts.append(host)
        if hasattr(module, "_bind_job_host"):
            module._bind_job_host(host, self._loop.loop)
            self._bound.append(module)

    def stop(self) -> None:
        """Stop every host (running jobs get their grace period), then the loop."""
        loop, self._loop = self._loop, None
        hosts, self.hosts = self.hosts, []
        bound, self._bound = self._bound, []
        self._documents = {}
        for module in bound:
            module._bind_job_host(None, None)
        if loop is None:
            return
        for host in reversed(hosts):
            try:
                grace = getattr(host, "close_grace_seconds", 10) + getattr(
                    host, "close_cancel_seconds", 15
                )
                loop.run(host.close(), grace + 5)
            except Exception as exc:  # noqa: BLE001 - stop every host on the way out
                logger.warning(f"Engine jobs: error stopping a job host: {exc}")
        transport, self._transport = self._transport, None
        if transport is not None:
            try:
                loop.run(transport.close(), 5)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Engine jobs: error closing the jobs connection: {exc}")
        loop.stop()
