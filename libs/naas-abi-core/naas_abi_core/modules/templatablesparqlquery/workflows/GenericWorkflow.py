from typing import Generic, Type, TypeVar

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.utils.SPARQL import SPARQLUtils
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class GenericWorkflow(Generic[T]):
    def __init__(
        self,
        name: str,
        description: str,
        sparql_template: str,
        arguments_model: Type[T],
        triple_store_service: TripleStoreService,
    ):
        self.name = name
        self.description = description
        self.sparql_template = sparql_template
        self.arguments_model = arguments_model
        self.triple_store_service = triple_store_service

    def run(self, parameters: T):
        try:
            from jinja2 import Template

            graph_names = " ".join(
                f"<{g}>" for g in self.triple_store_service.list_graphs()
            )

            template = Template(self.sparql_template)
            sparql_query = template.render(
                **parameters.model_dump(),
                graph_names=graph_names,
            )
            print(sparql_query)
            results = self.triple_store_service.query(sparql_query)

            return SPARQLUtils(self.triple_store_service).results_to_list(results)
        except Exception as e:
            return [{"error": str(e)}]

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name=self.name,
                description=self.description,
                func=lambda **kwargs: self.run(self.arguments_model(**kwargs)),
                args_schema=self.arguments_model,
            )
        ]
