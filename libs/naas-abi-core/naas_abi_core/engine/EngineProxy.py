from __future__ import annotations

from typing import TYPE_CHECKING, Dict

from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    ApiConfiguration,
)
from naas_abi_core.services.activity_log.ActivityLogService import ActivityLogService
from naas_abi_core.services.bus.BusService import BusService
from naas_abi_core.services.cache.CacheService import CacheService
from naas_abi_core.services.email.EmailService import EmailService
from naas_abi_core.services.event.EventService import EventService
from naas_abi_core.services.keyvalue.KeyValueService import KeyValueService
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService

if TYPE_CHECKING:
    from naas_abi_core.module.Module import BaseModule, ModuleDependencies


class ServicesProxy:
    __engine: IEngine
    __module_name: str
    __module_dependencies: ModuleDependencies
    __unlocked: bool

    def __init__(
        self,
        engine: IEngine,
        module_name: str,
        module_dependencies: ModuleDependencies,
        unlocked: bool = False,
    ):
        self.__engine = engine
        self.__module_name = module_name
        self.__module_dependencies = module_dependencies
        self.__unlocked = unlocked

    # def __accessible_services(self) -> List[Any]:
    #     engine_services = {
    #         type(service): service for service in self.__engine.services.all
    #     }

    #     for service_type in self.__module_dependencies.services:
    #         assert service_type in engine_services, (
    #             f"Service {service_type} not found in engine services"
    #         )

    #     return [
    #         service
    #         for service in engine_services.values()
    #         if type(service) in self.__module_dependencies.services
    #     ]

    def __ensure_access(self, service_type: type) -> None:
        if self.__unlocked:
            return

        if service_type not in self.__module_dependencies.services:
            raise ValueError(
                f"Module {self.__module_name} does not have access to {service_type}"
            )

    @property
    def object_storage(self) -> ObjectStorageService:
        self.__ensure_access(ObjectStorageService)

        return self.__engine.services.object_storage

    @property
    def triple_store(self) -> TripleStoreService:
        self.__ensure_access(TripleStoreService)

        return self.__engine.services.triple_store

    @property
    def vector_store(self) -> VectorStoreService:
        self.__ensure_access(VectorStoreService)

        return self.__engine.services.vector_store

    @property
    def secret(self) -> Secret:
        self.__ensure_access(Secret)

        return self.__engine.services.secret

    @property
    def bus(self) -> BusService:
        self.__ensure_access(BusService)

        return self.__engine.services.bus

    @property
    def kv(self) -> KeyValueService:
        self.__ensure_access(KeyValueService)

        return self.__engine.services.kv

    @property
    def email(self) -> EmailService:
        self.__ensure_access(EmailService)

        return self.__engine.services.email

    @property
    def cache(self) -> CacheService:
        self.__ensure_access(CacheService)

        return self.__engine.services.cache

    @property
    def activity_log(self) -> ActivityLogService:
        self.__ensure_access(ActivityLogService)

        return self.__engine.services.activity_log

    def activity_log_available(self) -> bool:
        if not self.__unlocked and ActivityLogService not in self.__module_dependencies.services:
            return False
        return self.__engine.services.activity_log_available()

    @property
    def events(self) -> EventService:
        self.__ensure_access(EventService)

        return self.__engine.services.events

    def events_available(self) -> bool:
        if not self.__unlocked and EventService not in self.__module_dependencies.services:
            return False
        return self.__engine.services.events_available()

    @property
    def model_registry(self) -> ModelRegistryService:
        # ModelRegistryService is intentionally exempt from
        # ``__ensure_access`` (see ``engine/context.py`` for the rationale):
        # the registry is a process-wide catalog every consumer should be able
        # to query, both via this proxy and via ``get_default_model_registry``.
        # Restricting it here would force every module that ships a ``models/``
        # directory — or that simply wants to resolve the default chat model —
        # to declare an otherwise-meaningless service dependency.
        return self.__engine.services.model_registry

    def model_registry_available(self) -> bool:
        # No dependency-declaration check on purpose — see ``model_registry``.
        return self.__engine.services.model_registry_available()


class EngineProxy:
    __engine: IEngine
    __module_name: str
    __module_dependencies: ModuleDependencies
    __unlocked: bool

    __services_proxy: ServicesProxy

    def __init__(
        self,
        engine: IEngine,
        module_name: str,
        module_dependencies: ModuleDependencies,
        unlocked: bool = False,
    ):
        self.__engine = engine
        self.__module_name = module_name
        self.__module_dependencies = module_dependencies
        self.__unlocked = unlocked
        self.__services_proxy = ServicesProxy(
            engine,
            module_name,
            module_dependencies,
            unlocked=unlocked,
        )

    @property
    def modules(self) -> Dict[str, BaseModule]:
        if self.__unlocked:
            return {
                module_name: module
                for module_name, module in self.__engine.modules.items()
                if module_name != self.__module_name
            }

        _modules = {}

        for module in self.__module_dependencies.modules:
            is_soft = module.endswith("#soft")
            module = module.replace("#soft", "")
            if module not in self.__engine.modules and is_soft:
                continue
            _modules[module] = self.__engine.modules[module]

        return _modules

    @property
    def services(self) -> ServicesProxy:
        return self.__services_proxy

    @property
    def api_configuration(self) -> ApiConfiguration:
        configuration = getattr(self.__engine, "configuration", None)
        if configuration is None or not hasattr(configuration, "api"):
            raise RuntimeError("Engine configuration API is not available")
        return configuration.api
