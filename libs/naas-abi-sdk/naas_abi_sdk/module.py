"""Lightweight ABI module lifecycle. No dependency on the engine runtime."""

from __future__ import annotations

import inspect
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from naas_abi_sdk.catalog import OPERATIONS
from naas_abi_sdk.client import ABIClient
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
        self, client: ABIClient, dependencies: ModuleDependencies, module_name: str = ""
    ):
        if dependencies.modules:
            raise ValueError(
                "Cross-module discovery is not implemented; declare service dependencies only"
            )
        self.services = ServicesProxy(client, dependencies, module_name)
        self.rpc = RPCServicesProxy(client, dependencies, module_name)


Config = TypeVar("Config", bound=ModuleConfiguration)


class BaseModule(Generic[Config]):
    """Subclass as ABIModule with Configuration, dependencies and lifecycle hooks.

    Hooks may be synchronous or async. Business operations use async typed SDK
    services. Engine-specific component discovery is deliberately not imported.
    """

    Configuration = ModuleConfiguration
    dependencies = ModuleDependencies()

    def __init__(self, engine: EngineProxy, configuration: Config):
        if not isinstance(configuration, self.Configuration):
            raise TypeError(
                "configuration must be an instance of ABIModule.Configuration"
            )
        self._engine = engine
        self._configuration = configuration

    @property
    def engine(self) -> EngineProxy:
        return self._engine

    @property
    def configuration(self) -> Config:
        return self._configuration

    @classmethod
    def get_dependencies(cls) -> ModuleDependencies:
        return cls.dependencies

    def on_load(self) -> None:
        pass

    def on_initialized(self) -> None:
        pass

    def on_unloaded(self) -> None:
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


async def run_module(
    module_type: type[BaseModule],
    *,
    url: str,
    token,
    configuration: ModuleConfiguration | None = None,
    timeout: float = 10.0,
    **connection_options,
) -> Any:
    """Own transport, dependency injection, ordered startup and guaranteed cleanup."""
    async with ABIClient(url, token, timeout=timeout, **connection_options) as client:
        module = module_type(
            EngineProxy(client, module_type.get_dependencies(), module_type.__module__),
            configuration if configuration is not None else module_type.Configuration(),
        )
        scope = _ModuleScope(module)
        token_context = _scope.set(scope)
        try:
            await _invoke(module.on_load)
            await _invoke(module.on_initialized)
            return await _invoke(module.run)
        finally:
            try:
                await _invoke(module.on_unloaded)
            finally:
                scope.active = False
                _scope.reset(token_context)
