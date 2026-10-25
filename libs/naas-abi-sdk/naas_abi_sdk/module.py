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
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from naas_abi_sdk import lifeline, telemetry
from naas_abi_sdk.apps import AppDescriptor, discover_apps
from naas_abi_sdk.catalog import OPERATIONS
from naas_abi_sdk.client import ABIClient
from naas_abi_sdk.components import by_name, discover_components
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
from naas_abi_sdk.ontologies import (
    OntologyFile,
    OntologyLoader,
    declared_ontologies,
    discover_ontologies,
    module_ontology_files,
)
from naas_abi_sdk.services import service_proxy
from naas_abi_sdk.transport import MODULE_INBOX_PREFIX

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
    # Web apps it serves over NATS. None: one per apps/<name>/manifest.json
    # next to the module's package (naas_abi_sdk.apps.discover_apps).
    apps: tuple[AppDescriptor, ...] | None = None
    # The .ttl files it sends to the engine's schema graph once the instance serves
    # (naas_abi_sdk.ontologies). None: every ontologies/**/*.ttl next to the module's
    # package, except under "sandbox". A tuple names the files, relative to ontologies/
    # (() sends none). A module with ontologies declares the triple_store service.
    ontologies: tuple[str | Path, ...] | None = None
    # Workflow and Pipeline classes (naas_abi_sdk.workflow, .pipeline). None:
    # every subclass found under the package's workflows/ and pipelines/
    # (recursively, tests and merely imported classes left out), like in-engine
    # modules. Their names (the class slug) are known before registration.
    workflows: tuple[type, ...] | None = None
    pipelines: tuple[type, ...] | None = None

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
        self._app_handlers: dict[str, Any] = {}
        self._workflows: dict[str, Any] = {}
        self._pipelines: dict[str, Any] = {}
        self._build_lock = asyncio.Lock()
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

    @classmethod
    def get_apps(cls) -> tuple[AppDescriptor, ...]:
        """The declared apps, else those found under the package's apps/."""
        if cls.apps is not None:
            return tuple(cls.apps)
        if "_discovered_apps" not in cls.__dict__:
            cls._discovered_apps = discover_apps(cls)
        return cls._discovered_apps

    @classmethod
    def get_ontologies(cls) -> tuple[OntologyFile, ...]:
        """The ontology files to send, as ``ontologies`` declares or discovery finds."""
        if "_ontology_files" not in cls.__dict__:
            cls._ontology_files = (
                discover_ontologies(cls)
                if cls.ontologies is None
                else declared_ontologies(cls, tuple(cls.ontologies))
            )
        return cls._ontology_files

    def expose_app(self, name: str, asgi_app) -> None:
        """Bind an ASGI application (FastAPI, Starlette) to a declared app during
        on_initialized. It answers the requests no file of the app's folder
        does; ``request.scope["abi"]["user_id"]`` is the signed-in Nexus user."""
        if name not in {app.name for app in self.get_apps()}:
            raise ValueError(f"Declare the app first: apps/{name}/manifest.json")
        if name in self._app_handlers:
            raise ValueError(f"App handler already registered: {name}")
        if not callable(asgi_app):
            raise TypeError("expose_app needs an ASGI application")
        self._app_handlers[name] = asgi_app

    @classmethod
    def get_workflow_classes(cls) -> dict[str, type]:
        """The declared workflows by name, else those found under workflows/."""
        return cls._component_classes("workflow", "workflows")

    @classmethod
    def get_pipeline_classes(cls) -> dict[str, type]:
        """The declared pipelines by name, else those found under pipelines/."""
        return cls._component_classes("pipeline", "pipelines")

    @classmethod
    def _component_classes(cls, kind: str, folder: str) -> dict[str, type]:
        def load_base() -> type:
            if kind == "workflow":
                from naas_abi_sdk.workflow import Workflow

                return Workflow
            from naas_abi_sdk.pipeline import Pipeline

            return Pipeline

        declared = getattr(cls, folder)
        if declared is not None:
            if declared:
                base = load_base()
                for item in declared:
                    if not (isinstance(item, type) and issubclass(item, base)):
                        raise TypeError(
                            f"{folder} must hold {base.__name__} subclasses"
                        )
            return by_name(kind, declared)
        key = f"_discovered_{folder}"
        if key not in cls.__dict__:
            setattr(
                cls, key, by_name(kind, discover_components(cls, folder, load_base))
            )
        return dict(cls.__dict__[key])

    def expose_workflow(self, name: str, workflow) -> None:
        """Bind a workflow instance during on_initialized, for a class
        that needs arguments to be built (no ``New``, no empty configuration)."""
        self._expose(
            "workflow", self.get_workflow_classes(), self._workflows, name, workflow
        )

    def expose_pipeline(self, name: str, pipeline) -> None:
        """Bind a pipeline instance during on_initialized, like expose_workflow."""
        self._expose(
            "pipeline", self.get_pipeline_classes(), self._pipelines, name, pipeline
        )

    @staticmethod
    def _expose(
        kind: str, declared: dict[str, type], bound: dict[str, Any], name: str, instance
    ) -> None:
        if name not in declared:
            raise ValueError(
                f"Declare the {kind} first: a {kind.capitalize()} subclass named "
                f"{name!r} under {kind}s/ (known: {sorted(declared)})"
            )
        if name in bound:
            raise ValueError(f"{kind.capitalize()} already registered: {name}")
        if not isinstance(instance, declared[name]):
            raise TypeError(
                f"{name!r} is a {declared[name].__name__}, not {type(instance)}"
            )
        bound[name] = instance

    def get_workflow(self, name: str):
        """The built workflow named ``name`` (the slug of its class name)."""
        return self._bound("workflow", self._workflows, name)

    def get_pipeline(self, name: str):
        """The built pipeline named ``name`` (the slug of its class name)."""
        return self._bound("pipeline", self._pipelines, name)

    def get_workflows(self) -> dict[str, Any]:
        """Every built workflow by name; empty until on_initialized has run."""
        return dict(self._workflows)

    def get_pipelines(self) -> dict[str, Any]:
        """Every built pipeline by name; empty until on_initialized has run."""
        return dict(self._pipelines)

    @staticmethod
    def _bound(kind: str, bound: dict[str, Any], name: str):
        try:
            return bound[name]
        except KeyError:
            raise ValueError(
                f"No {kind} named {name!r} is built (known: {sorted(bound)}); "
                "they are built after on_initialized, or by an earlier "
                "`await self.build_processes()`"
            ) from None

    async def build_processes(self) -> None:
        """Build every declared workflow and pipeline not yet bound.

        ``run_module`` calls it after ``on_initialized``. Call it yourself in
        ``on_initialized`` when an agent created there needs their tools::

            self.expose_workflow("needs_args_workflow", instance)  # first
            await self.build_processes()
            tools = self.get_workflow("greet_workflow").as_tools()

        Idempotent: a class already bound or built is left alone, so bind the
        ones that need arguments with ``expose_*`` before calling it. A class
        that is neither buildable nor bound fails startup: the module declares
        it, so callers expect it.
        """
        async with self._build_lock:
            for kind, declared, bound in (
                ("workflow", self.get_workflow_classes(), self._workflows),
                ("pipeline", self.get_pipeline_classes(), self._pipelines),
            ):
                for name, cls in declared.items():
                    if name not in bound:
                        bound[name] = await self._build(kind, name, cls)

    async def _build(self, kind: str, name: str, cls: type) -> Any:
        try:
            instance, reason = await cls.build(self)
        except Exception as exc:
            raise RuntimeError(
                f"Building {kind} {cls.__name__} ({name!r}) failed: {exc!r}"
            ) from exc
        if instance is None:
            raise ValueError(
                f"The {kind} {cls.__name__} ({name!r}) cannot be built: "
                f"{reason}. Give it a classmethod New(module), or bind an "
                f"instance in on_initialized with self.expose_{kind}({name!r}, instance)."
            )
        if not isinstance(instance, cls):
            raise TypeError(
                f"{cls.__name__}.New(module) must return a {cls.__name__}"
            )
        return instance

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


async def _drain_hosts(
    agent_host, job_host, model_host, timeout: float, app_host=None
) -> None:
    """Stop new work and wait for runs, jobs and app requests that already started."""
    if model_host is not None:
        model_host.closing = True
    waits = []
    if app_host is not None:
        waits.append(asyncio.create_task(app_host.drain(timeout)))
    if agent_host is not None:
        waits.append(asyncio.create_task(agent_host.drain(timeout)))
    if job_host is not None:
        waits.append(asyncio.create_task(job_host.drain(timeout)))
    # One host failing to drain does not cut the others' wait short.
    for result in await asyncio.gather(*waits, return_exceptions=True):
        if isinstance(result, Exception):
            logging.getLogger(__name__).warning("Draining failed", exc_info=result)


async def _host_jobs(job_host, module) -> None:
    await job_host.start()
    # The module's own triggers (atrigger_job) go through this host.
    module._bind_job_host(job_host, asyncio.get_running_loop())


async def _host_jobs_after_cutover(registration, job_host, module, refresh) -> None:
    """Host the jobs once this generation serves (READY or DEGRADED).

    Runs until the runner cancels it, so only a failure to host ends it. A
    process asked to drain first never hosts them.
    """
    draining = registration.drain_requested
    while registration.status not in ("READY", "DEGRADED") and not draining.is_set():
        await asyncio.sleep(refresh)
    if not draining.is_set():
        await _host_jobs(job_host, module)
    await asyncio.Event().wait()


async def _cancel(task: asyncio.Task | None) -> None:
    if task is not None and not task.done():
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


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
    # Before any connection: a file the engine would refuse, or ontologies without the
    # triple_store dependency, stop the module here, not in a background task.
    ontology_files = module_ontology_files(module_type, identity)
    # Names are known (and a bad folder fails) before anything connects.
    module_type.get_workflow_classes()
    module_type.get_pipeline_classes()
    # Spans export when OTEL_EXPORTER_OTLP_ENDPOINT is set (needs naas-abi-sdk[otel]).
    telemetry.configure_from_env(identity)
    # Named after the module so the broker's /connz shows which module is which.
    connection_options.setdefault("name", f"{identity}@{socket.gethostname()}")
    # A module reads its replies on the module inbox prefix, however it logs in
    # (URL, user/password options, creds or token): the broker user `module` may
    # not subscribe to _INBOX.>, where the engine's replies go.
    connection_options.setdefault("inbox_prefix", MODULE_INBOX_PREFIX)
    # NATS gone for good stops the module (SIGTERM drains it), and its supervisor
    # restarts it, instead of a process that serves nothing.
    async with (
        ABIClient(url, token, timeout=timeout, **connection_options) as client,
        lifeline.stopping_on_loss(),
    ):
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
        app_host = None
        job_host = None
        jobs_after_cutover: asyncio.Task | None = None
        ontologies_task: asyncio.Task | None = None
        health_server = None
        try:
            await _invoke(module.on_load)
            if registration:
                await registration.start()
                await module.engine.modules.wait_ready(discovery)
            await _invoke(module.on_initialized)
            await module.build_processes()
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
            apps = module_type.get_apps()
            if apps:
                if registration is None:
                    raise ValueError("App hosting requires discovery")
                from naas_abi_sdk.app_host import AppHost

                app_host = AppHost(
                    registration,
                    {a.name: (a, module._app_handlers.get(a.name)) for a in apps},
                )
                await app_host.start()
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
                if not registration.rollout_id:
                    await _host_jobs(job_host, module)
                else:
                    # Before this instance can serve: a trigger for a job only
                    # this generation declares waits in its consumer.
                    await job_host.prepare()
            if registration:
                registration.initialized = True
                await registration.renew()
            if job_host is not None and registration and registration.rollout_id:
                # Schedules and consumers are module-wide. A STAGED generation
                # leaves them to the serving one until its rollout cuts over.
                if registration.status == "STAGED":
                    jobs_after_cutover = asyncio.create_task(
                        _host_jobs_after_cutover(
                            registration,
                            job_host,
                            module,
                            discovery.refresh_seconds if discovery else 2.0,
                        )
                    )
                else:
                    await _host_jobs(job_host, module)
            if ontology_files:
                # Once this instance serves (READY or DEGRADED, never while STAGED), in
                # the background: a failed load is logged and retried, and does not
                # change readiness. It is not watched: it never ends the module.
                ontologies_task = asyncio.create_task(
                    OntologyLoader(
                        module.engine.services.triple_store,
                        identity,
                        ontology_files,
                        serving=(
                            (lambda: registration.status in ("READY", "DEGRADED"))
                            if registration is not None
                            else (lambda: True)
                        ),
                        stopping=(
                            registration.drain_requested.is_set
                            if registration is not None
                            else (lambda: False)
                        ),
                        poll_seconds=discovery.refresh_seconds if discovery else 2.0,
                    ).run()
                )
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
            if jobs_after_cutover is not None:
                watched.add(jobs_after_cutover)
            try:
                done, _ = await asyncio.wait(
                    watched, return_when=asyncio.FIRST_COMPLETED
                )
                if jobs_after_cutover in done:
                    await jobs_after_cutover  # it ends only when hosting failed
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
                    await _cancel(jobs_after_cutover)
                    await _cancel(ontologies_task)
                    await _drain_hosts(
                        agent_host,
                        job_host,
                        model_host,
                        drain_timeout_seconds,
                        app_host,
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
                await _cancel(jobs_after_cutover)
                await _cancel(ontologies_task)
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
                if app_host:
                    await app_host.close()
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
