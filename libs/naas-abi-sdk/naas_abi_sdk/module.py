"""Lightweight ABI module lifecycle. No dependency on the engine runtime."""

from __future__ import annotations

import asyncio
import inspect
import logging
import math
import os
import signal
import socket
from collections.abc import Awaitable
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from naas_abi_sdk import telemetry
from naas_abi_sdk.catalog import OPERATIONS
from naas_abi_sdk.client import ABIClient
from naas_abi_sdk.discovery import (
    AgentDescriptor,
    DiscoveryClient,
    DiscoveryConfiguration,
    DiscoverySession,
    ModelDescriptor,
    ModulesProxy,
    module_descriptor,
    validate_rollout_id,
)
from naas_abi_sdk.health import HealthServer
from naas_abi_sdk.jobs import JobsMixin
from naas_abi_sdk.services import service_proxy

if TYPE_CHECKING:
    from naas_abi_sdk.bus import BusClient
    from naas_abi_sdk.services import (
        ActivityLogService,
        CacheService,
        CodingEnvironmentService,
        DatasetService,
        DocumentService,
        EmailService,
        EventService,
        KeyValueService,
        ModelRegistryService,
        ObjectStorageService,
        SecretService,
        SourceControlService,
        TripleStoreService,
        VectorStoreService,
    )


@dataclass(frozen=True)
class ModuleDependencies:
    services: tuple[str, ...] = ()
    modules: tuple[str, ...] = ()


@dataclass
class ModuleConfiguration:
    global_config: dict[str, Any] = field(default_factory=dict)


class _ServicesAccess:
    """Dependency declarations are an API boundary, not broker authorization."""

    def __init__(
        self, client: ABIClient, dependencies: ModuleDependencies, module_name: str = ""
    ):
        self._client = client
        self._module_name = module_name
        self._proxies = {}
        self._aliases = {"kv": "keyvalue", "events": "event"}
        self._allowed = {
            self._aliases.get(name, name) for name in dependencies.services
        }
        unknown = self._allowed - (set(OPERATIONS) | {"bus", "kv", "events"})
        if unknown:
            raise ValueError(f"Unknown remote services: {sorted(unknown)}")


class ServicesProxy(_ServicesAccess):
    activity_log: ActivityLogService
    cache: CacheService
    coding_environment: CodingEnvironmentService
    dataset: DatasetService
    document: DocumentService
    email: EmailService
    event: EventService
    events: EventService
    keyvalue: KeyValueService
    kv: KeyValueService
    object_storage: ObjectStorageService
    secret: SecretService
    source_control: SourceControlService
    triple_store: TripleStoreService
    vector_store: VectorStoreService
    model_registry: ModelRegistryService
    bus: BusClient

    def __getattr__(self, name: str):
        if name.endswith("_available"):
            service = name.removesuffix("_available")
            return lambda: self._aliases.get(service, service) in self._allowed
        canonical = self._aliases.get(name, name)
        if canonical not in self._allowed:
            raise ValueError(f"Module did not declare service dependency: {name}")
        if canonical not in self._proxies:
            client = getattr(self._client, canonical)
            if canonical == "document":
                client = client.for_namespace(self._module_name)
            self._proxies[canonical] = service_proxy(
                canonical, client, self._client.bus
            )
        return self._proxies[canonical]


class RPCServicesProxy(_ServicesAccess):
    """Explicit protobuf access, with the same dependency and namespace checks."""

    def __getattr__(self, name: str):
        if name.endswith("_available"):
            service = name.removesuffix("_available")
            return lambda: self._aliases.get(service, service) in self._allowed
        canonical = self._aliases.get(name, name)
        if canonical not in self._allowed:
            raise ValueError(f"Module did not declare service dependency: {name}")
        client = getattr(self._client, canonical)
        return (
            client.for_namespace(self._module_name)
            if canonical == "document"
            else client
        )


class EngineProxy:
    def __init__(
        self,
        client: ABIClient,
        dependencies: ModuleDependencies,
        module_name: str = "",
        discovery: DiscoveryClient | None = None,
    ):
        if dependencies.modules and discovery is None:
            raise ValueError("Module dependencies require discovery configuration")
        self.modules = (
            ModulesProxy(discovery, dependencies.modules) if discovery else None
        )
        self.services = ServicesProxy(client, dependencies, module_name)
        self.rpc = RPCServicesProxy(client, dependencies, module_name)


Config = TypeVar("Config", bound=ModuleConfiguration)


class BaseModule(JobsMixin, Generic[Config]):
    """Subclass as ABIModule with Configuration, dependencies and lifecycle hooks.

    Hooks may be synchronous or async. Business operations use async typed SDK
    services. Engine-specific component discovery is deliberately not imported.
    """

    Configuration = ModuleConfiguration
    dependencies = ModuleDependencies()
    module_id: str | None = None
    package_version: str = "0.0.0"
    contract_major: int = 1
    agents: tuple[AgentDescriptor, ...] = ()
    models: tuple[ModelDescriptor, ...] = ()

    def __init__(self, engine: EngineProxy, configuration: Config):
        if not isinstance(configuration, self.Configuration):
            raise TypeError(
                "configuration must be an instance of ABIModule.Configuration"
            )
        self._engine = engine
        self._configuration = configuration
        self._discovery_session: DiscoverySession | None = None
        self._agent_handlers = {}
        self._model_handlers = {}
        self._health_port: int | None = None

    @property
    def engine(self) -> EngineProxy:
        return self._engine

    @property
    def configuration(self) -> Config:
        return self._configuration

    def expose_agent(self, name: str, handler) -> None:
        """Bind an async agent handler during on_initialized, before readiness."""
        descriptor = next((a for a in self.agents if a.name == name), None)
        if descriptor is None or "agent.invoke.v1" not in descriptor.capabilities:
            raise ValueError(
                "Declare an AgentDescriptor with agent.invoke.v1 capability first"
            )
        if name in self._agent_handlers:
            raise ValueError(f"Agent handler already registered: {name}")
        if not inspect.iscoroutinefunction(handler.invoke):
            raise TypeError(
                "Agent handler.invoke must be async; use the core adapter for synchronous agents"
            )
        self._agent_handlers[name] = handler

    def expose_model(self, name: str, handler) -> None:
        """Bind an async chat handler during on_initialized, before readiness.

        ``invoke(messages)`` may return text. ``invoke(messages, *, tools, tool_options)``
        may return an ``AIMessage`` with tool calls. The caller's agent runs the tools.
        """
        descriptor = next((model for model in self.models if model.name == name), None)
        if descriptor is None or descriptor.kind != "chat":
            raise ValueError("Declare a chat ModelDescriptor first")
        if name in self._model_handlers:
            raise ValueError(f"Model handler already registered: {name}")
        if not inspect.iscoroutinefunction(handler.invoke):
            raise TypeError("Model handler.invoke must be async")
        self._model_handlers[name] = handler

    @property
    def discovery_status(self) -> str:
        """Last confirmed membership state; lookups still validate targets live."""
        session = self._discovery_session
        if session is None:
            return "DISABLED"
        return session.current_status

    @property
    def health_port(self) -> int | None:
        """Bound probe port, once `ABI_HEALTH_PORT` or `health_port` started it."""
        return self._health_port

    @classmethod
    def get_dependencies(cls) -> ModuleDependencies:
        return cls.dependencies

    # Lifecycle hooks may be sync or async: run_module awaits what they return.
    def on_load(self) -> None | Awaitable[None]:
        pass

    def on_initialized(self) -> None | Awaitable[None]:
        pass

    def on_unloaded(self) -> None | Awaitable[None]:
        pass

    async def run(self) -> Any:
        raise NotImplementedError("Implement your remote module's run method")


@dataclass
class _ModuleScope:
    module: BaseModule
    active: bool = True


_scope: ContextVar[_ModuleScope | None] = ContextVar("abi_module_scope", default=None)


def current_module() -> BaseModule:
    """Return this task's running module, not a class-wide registry entry.

    Available in lifecycle hooks and run(), including awaited child tasks and
    asyncio.to_thread. Pass dependencies explicitly to raw threads or external
    callbacks. Detached tasks cannot use this helper after the module unloads.
    """
    scope = _scope.get()
    if scope is None or not scope.active:
        raise RuntimeError(
            "No active module context; pass the module explicitly or use run_module"
        )
    return scope.module


async def _invoke(hook):
    result = hook()
    return await result if inspect.isawaitable(result) else result


async def _drain_hosts(agent_host, job_host, model_host, timeout: float) -> None:
    """Stop new work and wait for runs and jobs that already started."""
    if model_host is not None:
        model_host.closing = True
    waits = []
    if agent_host is not None:
        waits.append(asyncio.create_task(agent_host.drain(timeout)))
    if job_host is not None:
        waits.append(asyncio.create_task(job_host.drain(timeout)))
    if waits:
        await asyncio.gather(*waits)


def _rollout(discovery: DiscoveryConfiguration) -> tuple[str, tuple[str, ...]]:
    rollout_id = validate_rollout_id(
        discovery.rollout_id or os.environ.get("ABI_ROLLOUT_ID", "")
    )
    modules = discovery.rollout_modules or tuple(
        part.strip()
        for part in os.environ.get("ABI_ROLLOUT_MODULES", "").split(",")
        if part.strip()
    )
    if modules and not rollout_id:
        raise ValueError("Rollout modules require a rollout id")
    return rollout_id, modules


def _health_bind(port: int | None, host: str) -> tuple[str, int] | None:
    """Where the probe listens. Unset means the process opens no port."""
    if port is None:
        raw = os.environ.get("ABI_HEALTH_PORT", "").strip()
        if not raw:
            return None
        if not raw.isascii() or not raw.isdigit():
            raise ValueError("ABI_HEALTH_PORT must be an integer from 0 to 65535")
        port = int(raw)
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("Health port must be an integer from 0 to 65535")
    bind_host = host or os.environ.get("ABI_HEALTH_HOST", "").strip() or "0.0.0.0"
    return bind_host, port


async def run_module(
    module_type: type[BaseModule],
    *,
    url: str,
    token,
    configuration: ModuleConfiguration | None = None,
    timeout: float = 10.0,
    agent_idle_timeout_seconds: float = 300.0,
    discovery: DiscoveryConfiguration | None = None,
    drain_timeout_seconds: float = 300.0,
    health_port: int | None = None,
    health_host: str = "",
    **connection_options,
) -> Any:
    """Own transport, dependency injection, ordered startup and guaranteed cleanup."""
    if not math.isfinite(drain_timeout_seconds) or drain_timeout_seconds <= 0:
        raise ValueError("Drain timeout must be finite and positive")
    probe = _health_bind(health_port, health_host)
    identity = module_type.module_id or module_type.__module__
    # Spans export when OTEL_EXPORTER_OTLP_ENDPOINT is set (needs naas-abi-sdk[otel]).
    telemetry.configure_from_env(identity)
    # Named after the module so the broker's /connz shows which module is which.
    connection_options.setdefault("name", f"{identity}@{socket.gethostname()}")
    async with ABIClient(url, token, timeout=timeout, **connection_options) as client:
        dependencies = module_type.get_dependencies()
        discovery_client = (
            DiscoveryClient(client._transport, discovery.project) if discovery else None
        )
        module = module_type(
            EngineProxy(client, dependencies, identity, discovery_client),
            configuration if configuration is not None else module_type.Configuration(),
        )
        scope = _ModuleScope(module)
        token_context = _scope.set(scope)
        rollout_id, rollout_modules = _rollout(discovery) if discovery else ("", ())
        registration = (
            DiscoverySession(
                discovery_client,
                module_descriptor(module_type, identity, dependencies.modules),
                rollout_id=rollout_id,
                rollout_modules=rollout_modules,
            )
            if discovery_client
            else None
        )
        module._discovery_session = registration
        work = None
        agent_host = None
        model_host = None
        job_host = None
        health_server = None
        try:
            await _invoke(module.on_load)
            if registration:
                await registration.start()
                await module.engine.modules.wait_ready(discovery)
            await _invoke(module.on_initialized)
            declared = {
                a.name for a in module.agents if "agent.invoke.v1" in a.capabilities
            }
            if declared != set(module._agent_handlers):
                raise ValueError(
                    "Every invocable agent must have a handler before module readiness"
                )
            if module._agent_handlers:
                if registration is None or "document" not in dependencies.services:
                    raise ValueError(
                        "Agent hosting requires discovery and a document service dependency"
                    )
                from naas_abi_sdk.agent_host import AgentHost

                agent_host = AgentHost(
                    registration,
                    module.engine.services.document,
                    module._agent_handlers,
                    idle_timeout_seconds=agent_idle_timeout_seconds,
                )
                await agent_host.start()
            declared_models = {
                model.name for model in module.models if model.kind == "chat"
            }
            if declared_models != set(module._model_handlers):
                raise ValueError(
                    "Every declared chat model must have a handler before module readiness"
                )
            if module._model_handlers:
                if registration is None:
                    raise ValueError("Model hosting requires discovery")
                from naas_abi_sdk.model_host import ModelHost

                model_host = ModelHost(registration, module._model_handlers)
                await model_host.start()
            if module.missing_job_handlers():
                raise ValueError(
                    "Every declared job must have a handler before module readiness"
                )
            if module._job_handlers:
                if registration is None or "document" not in dependencies.services:
                    raise ValueError(
                        "Job hosting requires discovery and a document service dependency"
                    )
                from naas_abi_sdk.job_host import JobHost

                job_host = JobHost(
                    client._transport,
                    module.engine.services.document,
                    identity,
                    discovery.project,
                    {j.name: (j, module._job_handlers[j.name]) for j in module.jobs},
                    instance_id=registration.instance_id,
                )
                await job_host.start()
                # The module's own triggers (atrigger_job) go through this host.
                module._bind_job_host(job_host, asyncio.get_running_loop())
            if registration:
                registration.initialized = True
                await registration.renew()
            if probe is not None:
                health_server = HealthServer(
                    lambda: module.discovery_status, probe[0], probe[1]
                )
                await health_server.start()
                module._health_port = health_server.port
            work = asyncio.create_task(_invoke(module.run))
            stop = (
                registration.drain_requested
                if registration is not None
                else asyncio.Event()
            )
            loop = asyncio.get_running_loop()
            installed: list[signal.Signals] = []

            def _request_drain() -> None:
                if registration is not None:
                    registration.draining = True
                stop.set()

            try:
                for sig in (signal.SIGTERM, signal.SIGINT):
                    loop.add_signal_handler(sig, _request_drain)
                    installed.append(sig)
            except (NotImplementedError, RuntimeError):
                installed.clear()
            stop_task = asyncio.create_task(stop.wait())
            watched = {work, stop_task}
            if registration is not None and registration.task is not None:
                watched.add(registration.task)
            try:
                done, _ = await asyncio.wait(
                    watched, return_when=asyncio.FIRST_COMPLETED
                )
                if registration is not None and registration.task in done:
                    await registration.task
                    return await work
                if stop_task in done and work not in done:
                    if registration is not None:
                        registration.draining = True
                        try:
                            await registration.renew()
                        except Exception:
                            logging.getLogger(__name__).warning(
                                "Could not mark module draining", exc_info=True
                            )
                    await _drain_hosts(
                        agent_host,
                        job_host,
                        model_host,
                        drain_timeout_seconds,
                    )
                    if not work.done():
                        work.cancel()
                    await asyncio.gather(work, return_exceptions=True)
                    return None
                return await work
            finally:
                if not stop_task.done():
                    stop_task.cancel()
                    await asyncio.gather(stop_task, return_exceptions=True)
                for sig in installed:
                    loop.remove_signal_handler(sig)
        finally:
            try:
                if health_server is not None:
                    await health_server.close()
                if work:
                    if not work.done():
                        work.cancel()
                    await asyncio.gather(work, return_exceptions=True)
                if registration:
                    registration.draining = True
                    try:
                        await registration.renew()
                    except Exception:
                        logging.getLogger(__name__).warning(
                            "Could not mark module draining", exc_info=True
                        )
                if job_host:
                    module._bind_job_host(None, None)
                    await job_host.close()
                if model_host:
                    await model_host.close()
                if agent_host:
                    await agent_host.close()
                await _invoke(module.on_unloaded)
            finally:
                try:
                    if registration:
                        await registration.close()
                finally:
                    scope.active = False
                    _scope.reset(token_context)
