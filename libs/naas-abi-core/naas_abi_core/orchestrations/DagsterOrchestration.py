from dagster import Definitions
from naas_abi_core.orchestrations.Orchestrations import Orchestrations


class DagsterOrchestration(Orchestrations):
    __definitions: Definitions
    
    def __init__(self, definitions: Definitions):
        self.__definitions = definitions

    @property
    def definitions(self) -> Definitions:
        return self.__definitions
    
    @classmethod
    def New(cls) -> "DagsterOrchestration":
        return cls(definitions=Definitions())