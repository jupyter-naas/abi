from typing import Dict, List

from naas_abi_core import logger
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    EngineConfiguration,
)
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.module.Module import ModuleDependencies
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService


class EngineServiceLoader:
    __configuration: EngineConfiguration

    def __init__(self, configuration: EngineConfiguration):
        self.__configuration = configuration

    def load_services(
        self, module_dependencies: Dict[str, ModuleDependencies]
    ) -> IEngine.Services:
        services_to_load: List[type] = []

        for _, module_dependency in module_dependencies.items():
            services_to_load.extend(module_dependency.services)

        services_to_load = list(set(services_to_load))
        logger.debug(f"Services to load: {services_to_load}")

        return IEngine.Services(
            self.__configuration.services.object_storage.load()
            if ObjectStorageService in services_to_load
            else None,
            self.__configuration.services.triple_store.load()
            if TripleStoreService in services_to_load
            else None,
            self.__configuration.services.vector_store.load()
            if VectorStoreService in services_to_load
            else None,
            self.__configuration.services.secret.load()
            if Secret in services_to_load
            else None,
        )
