"""Host the jobs of engine modules in this process (NATS mode only).

Engine modules declare jobs exactly like SDK modules (``naas_abi_core.module.jobs``).
Each module with jobs gets one SDK ``JobHost``: same stream, subjects, consumers
and run records as a standalone module, so callers cannot tell them apart.

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
    interrupted on timeout or cancel (see ``SyncJobRunner``)."""
    from naas_abi_sdk.jobs import is_async_callable

    if is_async_callable(handler):
        return handler
    return SyncJobRunner(handler, interrupt_grace_seconds=interrupt_grace_seconds)


class _LoopThread:
    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(
            target=self.loop.run_forever, daemon=True, name=LOOP_THREAD_NAME
        )
        self.thread.start()

    def run(self, coro: Any, timeout: float) -> Any:
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)

    def stop(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=5.0)
        if not self.thread.is_alive():
            self.loop.close()


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
        self._loop: _LoopThread | None = None
        self._transport: Any = None

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
                f"Engine jobs need NATS mode; not hosting the jobs of {sorted(with_jobs)}"
            )
            return
        if not self.configuration.jobs.enabled:
            logger.info(
                f"Engine jobs disabled; not hosting the jobs of {sorted(with_jobs)}"
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

        self._loop = _LoopThread()
        try:
            for module_id, module in with_jobs.items():
                self._start_host(module_id, module)
        except BaseException:
            self.stop()
            raise
        logger.info(
            f"Engine jobs: hosting {sum(len(m.jobs) for m in with_jobs.values())} job(s) "
            f"of {sorted(with_jobs)} in project {self.project!r}"
        )

    def _start_host(self, module_id: str, module: Any) -> None:
        assert self._loop is not None and self.configuration is not None
        if self._transport is None:
            from naas_abi_core.engine.nats_auth import issue_service_token
            from naas_abi_sdk.transport import Transport

            secret = self.configuration.jwt_secret
            self._transport = Transport(
                self.configuration.nats_url,
                lambda: issue_service_token(ENGINE_IDENTITY, secret),
            )
        handlers = module._job_handlers
        host = self.host_factory(
            self._transport,
            self.documents_factory(self._transport, module_id),
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
            **self.host_options,
        )
        self._loop.run(host.start(), START_TIMEOUT_SECONDS)
        self.hosts.append(host)

    def stop(self) -> None:
        """Stop every host (running jobs get their grace period), then the loop."""
        loop, self._loop = self._loop, None
        hosts, self.hosts = self.hosts, []
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
