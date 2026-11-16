from typing import Generic, TypeVar

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.utils.Logger import logger
from naas_abi_core.utils.SPARQL import SPARQLUtils
from naas_abi_core.utils.SPARQLTemplate import SPARQLTemplate
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class GenericWorkflow(Generic[T]):
    def __init__(
        self,
        name: str,
        description: str,
        sparql_template: str,
        arguments_model: type[T],
        triple_store_service: TripleStoreService,
    ):
        self.name = name
        self.description = description
        self.sparql_template = sparql_template
        self.arguments_model = arguments_model
        self.triple_store_service = triple_store_service
        # The arguments come from a model: rendered so that none can change
        # the query (escaped in a literal, checked in an IRI or a bare token).
        self.template = SPARQLTemplate(sparql_template)

    def run(self, parameters: T):
        try:
            sparql_query = self.template.render(**parameters.model_dump())
            # It holds the model's arguments: DEBUG only.
            logger.debug(f"{self.name} query: {sparql_query}")
            results = self.triple_store_service.query(sparql_query)

            return SPARQLUtils(self.triple_store_service).results_to_list(results)
        except Exception as e:  # noqa: BLE001
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
