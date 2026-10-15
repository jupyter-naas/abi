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


def as_engine(handler: Callable[..., Any]) -> Callable[..., Any]:
    """``handler``, run as the engine's service account: a job runs for no
    caller (``naas_abi_core.engine.call_context.as_service_account``)."""
    from naas_abi_core.engine.call_context import as_service_account

    async def run(ctx: Any) -> Any:
        with as_service_account(ENGINE_IDENTITY):
            return await handler(ctx)

    return run


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


def _default_documents(transport: Any, module_id: str) -> Any:
    from naas_abi_sdk.document import DocumentClient
    from naas_abi_sdk.services.document import DocumentService

    return DocumentService(DocumentClient(transport).for_namespace(module_id))


def job_authorizer(iam: Any, secret: str, project: str, module_id: str) -> Any:
    """An engine job host's authorizer: the check discovery runs for a module's
    host (``discovery_service.require_job``), in process.

    The caller is the one the trigger or cancel message names (its token, as of
    when the trigger was stored, and its on-behalf-of user), verified with the
    engine's secret. A refusal is an ``RPCError`` the host records; IAM is asked
    off the jobs loop.
    """
    from naas_abi_core.engine.call_context import ON_BEHALF_OF_HEADER, use_call_context
    from naas_abi_core.engine.nats_auth import InvalidServiceTokenError
    from naas_abi_core.services.discovery.caller import caller_of
    from naas_abi_core.services.discovery.discovery_service import require_job
    from naas_abi_core.services.discovery.iam_catalog import CATALOG
    from naas_abi_core.services.iam.guard import ServiceGuard
    from naas_abi_core.services.iam.IAMPorts import PermissionDeniedError
    from naas_abi_sdk.transport import RPCError

    guard = ServiceGuard(CATALOG, lambda: iam)

    def check(operation, job, run_id, headers, stored_at) -> None:
        try:
            caller = caller_of(
                headers.get("Nats-Auth-Token", ""),
                headers.get(ON_BEHALF_OF_HEADER, ""),
                secret,
                at=stored_at.timestamp() if stored_at is not None else None,
            )
        except InvalidServiceTokenError as exc:
            raise RPCError("UNAUTHENTICATED", str(exc)) from exc
        try:
            with use_call_context(caller):
                require_job(guard, project, module_id, job, operation, run_id)
        except PermissionDeniedError as exc:
            raise RPCError("PERMISSION_DENIED", str(exc)) from exc

    async def authorize(operation, job, run_id, headers, stored_at) -> None:
        await asyncio.to_thread(check, operation, job, run_id, headers, stored_at)

    return authorize


def _module_iam(modules: Mapping[str, Any]) -> Any:
    """The engine's IAM, as its modules are wired with it."""
    for module in modules.values():
        services = getattr(getattr(module, "engine", None), "services", None)
        available = getattr(services, "iam_available", None)
        if callable(available) and available():
            return getattr(services, "iam", None)
    return None


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
        iam: Any = None,
    ) -> None:
        """``iam``: authorizes manual triggers and cancels (discovery:TriggerJob,
        CancelJobRun); by default the one the modules are wired with."""
        self.iam = iam
        self.configuration = configuration
        self.documents_factory = documents_factory
        self.host_factory = host_factory
        self.host_options = dict(host_options or {})
        self.hosts: list[Any] = []
        # Modules bound to their host, for their own triggers (trigger_job).
        self._bound: list[Any] = []
        self._loop: LoopThread | None = None
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

        if self.iam is None:
            self.iam = _module_iam(modules)
        self._loop = LoopThread()
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
            from naas_abi_core.engine.nats_naming import connection_name
            from naas_abi_sdk.transport import Transport

            secret = self.configuration.jwt_secret
            self._transport = Transport(
                self.configuration.nats_url,
                lambda: issue_service_token(ENGINE_IDENTITY, secret),
                name=connection_name("abi-engine:jobs"),
                forward_user=True,  # kernel calls, as the trusted engine identity
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
                    as_engine(
                        as_async_handler(
                            handlers[j.name],
                            interrupt_grace_seconds=self.configuration.jobs.interrupt_grace_seconds,
                        )
                    ),
                )
                for j in module.jobs
            },
            instance_id=f"engine-{uuid.uuid4().hex[:12]}",
            **(
                {}
                if self.iam is None
                else {
                    "authorize": job_authorizer(
                        self.iam,
                        self.configuration.jwt_secret,
                        self.project,
                        module_id,
                    )
                }
            ),
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
