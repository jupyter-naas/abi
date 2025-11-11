from abi.engine.engine_configuration.EngineConfiguration import EngineConfiguration
from abi.engine.IEngine import IEngine


class EngineServiceLoader:
    __configuration: EngineConfiguration

    def __init__(self, configuration: EngineConfiguration):
        self.__configuration = configuration

    def load_services(self) -> IEngine.Services:
        return IEngine.Services(
            self.__configuration.services.object_storage.load(),
            self.__configuration.services.triple_store.load(),
            self.__configuration.services.vector_store.load(),
            self.__configuration.services.secret.load(),
        )
