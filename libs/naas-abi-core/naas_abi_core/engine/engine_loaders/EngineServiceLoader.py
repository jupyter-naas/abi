from typing import Dict, List

from naas_abi_core import logger
from naas_abi_core.engine.engine_configuration.EngineConfiguration import \
    EngineConfiguration
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.module.Module import ModuleDependencies
from naas_abi_core.services.bus.BusService import BusService
from naas_abi_core.services.KeyValue.KVService import KVService
from naas_abi_core.services.object_storage.ObjectStorageService import \
    ObjectStorageService
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.triple_store.TripleStoreService import \
    TripleStoreService
from naas_abi_core.services.vector_store.VectorStoreService import \
    VectorStoreService

SERVICES_DEPENDENCIES = {
    TripleStoreService: [BusService],
}

class EngineServiceLoader:
    __configuration: EngineConfiguration

    def __init__(self, configuration: EngineConfiguration):
        self.__configuration = configuration

    def _should_load_service(self, service_type: type, services_to_load: List[type]) -> bool:
        if service_type in services_to_load:
            return True
        
        for service, dependencies in SERVICES_DEPENDENCIES.items():
            if service_type in dependencies and service in services_to_load:
                return True
        return False
        
    def load_services(
        self, module_dependencies: Dict[str, ModuleDependencies]
    ) -> IEngine.Services:
        services_to_load: List[type] = []

        for _, module_dependency in module_dependencies.items():
            services_to_load.extend(module_dependency.services)


        services_to_load = list(set(services_to_load))
        logger.debug(f"Services to load: {services_to_load}")

        services = IEngine.Services(
            object_storage=self.__configuration.services.object_storage.load()
            if self._should_load_service(ObjectStorageService, services_to_load)
            else None,
            triple_store=self.__configuration.services.triple_store.load()
            if self._should_load_service(TripleStoreService, services_to_load)
            else None,
            vector_store=self.__configuration.services.vector_store.load()
            if self._should_load_service(VectorStoreService, services_to_load)
            else None,
            secret=self.__configuration.services.secret.load()
            if self._should_load_service(Secret, services_to_load)
            else None,
            bus=self.__configuration.services.bus.load()
            if self._should_load_service(BusService, services_to_load)
            else None,
            kv=self.__configuration.services.kv.load()
            if self._should_load_service(KVService, services_to_load)
            else None,
        )
        services.wire_services()
        return services
