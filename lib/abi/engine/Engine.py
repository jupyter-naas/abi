from typing import Dict, List

from abi import logger
from abi.engine.engine_configuration.EngineConfiguration import EngineConfiguration
from abi.engine.engine_loaders.EngineModuleLoader import EngineModuleLoader
from abi.engine.engine_loaders.EngineOntologyLoader import EngineOntologyLoader
from abi.engine.engine_loaders.EngineServiceLoader import EngineServiceLoader
from abi.engine.IEngine import IEngine
from abi.module.Module import BaseModule


class Engine(IEngine):
    __configuration: EngineConfiguration
    __engine_module_loader: EngineModuleLoader
    __engine_service_loader: EngineServiceLoader

    __modules: Dict[
        str, BaseModule
    ]  # Must not set a default value to prevent modules to try to access modules inside constructors.

    __services: IEngine.Services

    @property
    def modules(self) -> Dict[str, BaseModule]:
        return self.__modules

    @property
    def services(self) -> IEngine.Services:
        return self.__services

    def __init__(self, configuration: str | None = None):
        # Load configuration
        self.__configuration = EngineConfiguration.load_configuration(configuration)
        self.__engine_module_loader = EngineModuleLoader(self.__configuration)
        self.__engine_service_loader = EngineServiceLoader(self.__configuration)

    def load(self, module_names: List[str] = []):
        logger.info("Loading engine services")
        self.__services = self.__engine_service_loader.load_services()
        logger.info("Engine services loaded")

        logger.info("Loading engine modules")
        self.__modules = self.__engine_module_loader.load_modules(self, module_names)
        logger.info("Engine modules loaded")

        logger.info("Loading engine ontologies")
        EngineOntologyLoader.load_ontologies(
            self.__services.triple_store,
            self.__engine_module_loader.ordered_modules,
        )
        logger.info("Engine ontologies loaded")

        logger.info("Initializing engine")
        self.on_initialized()
        logger.info("Engine initialized")

    def on_initialized(self):
        for module in self.__modules.values():
            module.on_initialized()


if __name__ == "__main__":
    engine = Engine()
    engine.load()
    print("Engine loaded successfully")
