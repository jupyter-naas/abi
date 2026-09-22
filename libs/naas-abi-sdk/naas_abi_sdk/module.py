"""Lightweight ABI module lifecycle. No dependency on the engine runtime."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from naas_abi_sdk.catalog import OPERATIONS
from naas_abi_sdk.client import ABIClient


@dataclass(frozen=True)
class ModuleDependencies:
    services: tuple[str, ...] = ()
    modules: tuple[str, ...] = ()


@dataclass
class ModuleConfiguration:
    global_config: dict[str, Any] = field(default_factory=dict)


class ServicesProxy:
    """Dependency declarations are an API boundary, not broker authorization."""

    def __init__(
        self, client: ABIClient, dependencies: ModuleDependencies, module_name: str = ""
    ):
        self._client = client
        self._module_name = module_name
        self._aliases = {"kv": "keyvalue", "events": "event"}
        self._allowed = {
            self._aliases.get(name, name) for name in dependencies.services
        }
        unknown = self._allowed - (set(OPERATIONS) | {"bus", "kv", "events"})
        if unknown:
            raise ValueError(f"Unknown remote services: {sorted(unknown)}")

    def __getattr__(self, name: str):
        if name.endswith("_available"):
            service = name.removesuffix("_available")
            return lambda: self._aliases.get(service, service) in self._allowed
        canonical = self._aliases.get(name, name)
        if canonical not in self._allowed:
            raise ValueError(f"Module did not declare service dependency: {name}")
        if canonical == "document":
            return self._client.document.for_namespace(self._module_name)
        return getattr(self._client, canonical)


class EngineProxy:
    def __init__(
        self, client: ABIClient, dependencies: ModuleDependencies, module_name: str = ""
    ):
        if dependencies.modules:
            raise ValueError(
                "Cross-module discovery is not implemented; declare service dependencies only"
            )
        self.services = ServicesProxy(client, dependencies, module_name)


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
        try:
            await _invoke(module.on_load)
            await _invoke(module.on_initialized)
            return await _invoke(module.run)
        finally:
            await _invoke(module.on_unloaded)
