from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.modules.templatablesparqlquery.workflows.TemplatableSparqlQueryLoader import (
    TemplatableSparqlQueryLoader,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService


class ABIModule(BaseModule):
    __workflows: list = []
    __tools: list = []

    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[], services=[TripleStoreService]
    )

    class Configuration(ModuleConfiguration):
        pass

    def on_initialized(self):
        self.__templatable_sparql_query_loader = TemplatableSparqlQueryLoader(
            self.engine.services.triple_store
        )
        self.__workflows = self.__templatable_sparql_query_loader.load_workflows()
        self.__tools = [
            tool for workflow in self.__workflows for tool in workflow.as_tools()
        ]

    def get_workflows(self):
        return self.__workflows

    def get_tools(self, tool_names: list[str] = []):
        if len(tool_names) == 0:
            return self.__tools
        else:
            return [tool for tool in self.__tools if tool.name in tool_names]
