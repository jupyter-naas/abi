from __future__ import annotations

from typing import TYPE_CHECKING, Dict

from abi.engine.IEngine import IEngine
from abi.services.object_storage.ObjectStorageService import ObjectStorageService
from abi.services.secret.Secret import Secret
from abi.services.triple_store.TripleStoreService import TripleStoreService
from abi.services.vector_store.VectorStoreService import VectorStoreService

if TYPE_CHECKING:
    from abi.module.Module import BaseModule, ModuleDependencies


class ServicesProxy:
    __engine: IEngine
    __module_name: str
    __module_dependencies: ModuleDependencies

    def __init__(
        self, engine: IEngine, module_name: str, module_dependencies: ModuleDependencies
    ):
        self.__engine = engine
        self.__module_name = module_name
        self.__module_dependencies = module_dependencies

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


class EngineProxy:
    __engine: IEngine
    __module_name: str
    __module_dependencies: ModuleDependencies

    __services_proxy: ServicesProxy

    def __init__(
        self,
        engine: IEngine,
        module_name: str,
        module_dependencies: ModuleDependencies,
    ):
        self.__engine = engine
        self.__module_name = module_name
        self.__module_dependencies = module_dependencies
        self.__services_proxy = ServicesProxy(engine, module_name, module_dependencies)

    @property
    def modules(self) -> Dict[str, BaseModule]:
        return {
            module_name: self.__engine.modules[module_name]
            for module_name in self.__module_dependencies.modules
        }

    @property
    def services(self) -> ServicesProxy:
        return self.__services_proxy
