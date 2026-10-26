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
from naas_abi_core.engine.nats_auth import TokenSource

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


def as_engine(
    handler: Callable[..., Any], identity: str = ENGINE_IDENTITY
) -> Callable[..., Any]:
    """``handler``, run as a service account of the engine's own (``identity``,
    by default the engine itself): a job runs for no caller
    (``naas_abi_core.engine.call_context.as_service_account``), unless its
    trigger was stored for a user: then the host runs it as ``identity`` for
    that user (``job_authorizer``), and that context is kept."""
    from naas_abi_core.engine.call_context import (
        as_service_account,
        current_call_context,
    )

    async def run(ctx: Any) -> Any:
        current = current_call_context()
        if current.on_behalf_of is not None and current.principal.name == identity:
            return await handler(ctx)
        with as_service_account(identity):
            return await handler(ctx)

    run.__wrapped__ = handler  # type: ignore[attr-defined]
    return run


def job_identity(iam: Any, module_id: str) -> str:
    """The account an engine module's jobs run as: ``job/<module_id>``, holding
    ``builtin.job`` only, created when first needed. Without an IAM service this
    engine owns (a client-role engine, tests) the jobs run as the engine."""
    from naas_abi_core.engine.call_context import as_service_account
    from naas_abi_core.services.iam import roles
    from naas_abi_core.services.iam.IAMPorts import IAMNotFoundError

    if iam is None or not hasattr(iam, "create_service_account"):
        return ENGINE_IDENTITY
    name = roles.job_account_name(module_id)
    with as_service_account(ENGINE_IDENTITY):
        try:
            account = iam.find_service_account(name)
        except IAMNotFoundError:
            account = iam.create_service_account(name)
        iam.attach_policy(roles.JOB, account.id)
    return name


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


def job_authorizer(
    iam: Any,
    verifier: Any,
    project: str,
    module_id: str,
    identity: str = ENGINE_IDENTITY,
) -> Any:
    """An engine job host's authorizer: the check discovery runs for a module's
    host (``discovery_service.require_job``), in process.

    The caller is the one the trigger or cancel message's token names (as of
    when the trigger was stored, with the user it acts for when it names one),
    verified against the engine's JWKS (``verifier``). A refusal is an ``RPCError`` the host records; IAM is asked
    off the jobs loop.

    An allowed trigger that ``api`` or ``engine`` stored for a user runs as the
    module's job account (``identity``) for that user, with the caller's scope;
    any other runs as the account alone (a module never hands a user to
    another, as with agents).
    """
    from naas_abi_core.engine.call_context import (
        CallContext,
        as_service_account,
        service_account,
        use_call_context,
    )
    from naas_abi_core.engine.nats_auth import (
        HOST_AUDIENCE_PREFIX,
        InvalidServiceTokenError,
        host_audience,
    )
    from naas_abi_core.services.discovery.caller import caller_of
    from naas_abi_core.services.discovery.discovery_service import require_job
    from naas_abi_core.services.discovery.iam_catalog import CATALOG
    from naas_abi_core.services.iam.guard import ServiceGuard
    from naas_abi_core.services.iam.IAMPorts import PermissionDeniedError
    from naas_abi_sdk.transport import RPCError

    guard = ServiceGuard(CATALOG, lambda: iam)
    # A trigger carries a host token the engine wrote, never a caller's own,
    # and one addressed to this host: the engine's, whose jobs these are.
    verifier = verifier.for_audiences((), prefixes=(HOST_AUDIENCE_PREFIX,))
    recipient: list[str] = []

    def host_token_audience() -> str:
        from naas_abi_core.services.iam.modules import subject_token

        if not recipient:
            with as_service_account("engine"):
                account = iam.find_service_account("engine")
            recipient.append(subject_token(account.id))
        return host_audience(recipient[0])

    def check(operation, job, run_id, headers, stored_at) -> CallContext | None:
        try:
            caller = caller_of(
                headers.get("Nats-Auth-Token", ""),
                verifier,
                at=stored_at.timestamp() if stored_at is not None else None,
            )
            if caller.audience != host_token_audience():
                raise InvalidServiceTokenError("the caller's token is for another host")
        except InvalidServiceTokenError as exc:
            raise RPCError("UNAUTHENTICATED", str(exc)) from exc
        try:
            with use_call_context(caller):
                require_job(guard, project, module_id, job, operation, run_id)
        except PermissionDeniedError as exc:
            raise RPCError("PERMISSION_DENIED", str(exc)) from exc
        first_party = caller.principal.name in (ENGINE_IDENTITY, "api")
        if operation != "trigger" or caller.on_behalf_of is None or not first_party:
            return None
        return CallContext(
            principal=service_account(identity),
            on_behalf_of=caller.on_behalf_of,
            scope=caller.scope,
            trace_id=caller.trace_id,
        )

    async def authorize(operation, job, run_id, headers, stored_at) -> Any:
        return await asyncio.to_thread(
            check, operation, job, run_id, headers, stored_at
        )

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
        credentials: TokenSource | None = None,
        documents_factory: Callable[[Any, str], Any] = _default_documents,
        host_factory: Callable[..., Any] = _default_host,
        host_options: Mapping[str, Any] | None = None,
        iam: Any = None,
    ) -> None:
        """``iam``: authorizes manual triggers and cancels (discovery:TriggerJob,
        CancelJobRun); by default the one the modules are wired with."""
        self.iam = iam
        self.configuration = configuration
        # The engine's own tokens (nats_credentials): the job host's kernel calls.
        self.credentials = credentials
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
        # The loop, the transport and the documents are made on first use, from any
        # thread (start, a request thread calling workflow(), a host's loop).
        self._lock = threading.RLock()

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

        if self.iam is None:
            self.iam = _module_iam(modules)
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
        with self._lock:
            if self._loop is None:
                self._loop = LoopThread()
            return self._loop

    def _ensure_transport(self) -> Any:
        assert self.configuration is not None
        with self._lock:
            if self._transport is None:
                from naas_abi_core.engine.nats_naming import connection_name
                from naas_abi_sdk.transport import Transport

                if self.credentials is None:
                    raise RuntimeError("Engine jobs need the engine's credentials")
                self._transport = Transport(
                    self.configuration.nats_url,
                    self.credentials.token,
                    name=connection_name("abi-engine:jobs"),
                    # Kernel calls carry the user a job runs for in a delegation, as
                    # the engine identity does (a job host runs for no user unless
                    # its trigger named one).
                    delegate=self.credentials.token_for,
                )
            return self._transport

    def module_documents(self, module_id: str) -> Any:
        """The documents of ``module_id``'s namespace: where its run records and
        journals are, for a workflow reading the runs of its children."""
        with self._lock:
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
        an unknown workflow's runs stay QUEUED. The proxy uses this loader's loop and
        connection, which ``stop()`` closes: do not keep it past the engine's
        shutdown (a later call would hang or fail with "Event loop is closed")."""
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
                    as_engine(
                        as_async_handler(
                            handlers[j.name],
                            interrupt_grace_seconds=self.configuration.jobs.interrupt_grace_seconds,
                        ),
                        job_identity(self.iam, module_id),
                    ),
                )
                for j in module.jobs
            },
            instance_id=f"engine-{uuid.uuid4().hex[:12]}",
            module_documents=self.module_documents,
            **(
                {}
                if self.iam is None
                else {
                    "authorize": job_authorizer(
                        self.iam,
                        self._verifier(),
                        self.project,
                        module_id,
                        job_identity(self.iam, module_id),
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

    def _verifier(self) -> Any:
        """IAM's own verifier in the serving engine, else its JWKS over NATS."""
        verifier = getattr(self.iam, "verifier", None)
        if callable(verifier):
            return verifier()
        from naas_abi_core.engine.nats_credentials import nats_verifier

        assert self.configuration is not None
        return nats_verifier(self.configuration.nats_url)

    def stop(self) -> None:
        """Stop every host (running jobs get their grace period), then the loop."""
        with self._lock:
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
        with self._lock:
            transport, self._transport = self._transport, None
        if transport is not None:
            try:
                loop.run(transport.close(), 5)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Engine jobs: error closing the jobs connection: {exc}")
        loop.stop()
