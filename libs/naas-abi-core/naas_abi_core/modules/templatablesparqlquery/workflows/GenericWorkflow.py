from functools import cache
from typing import Any, Generic, TypeVar

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.utils.Logger import logger
from naas_abi_core.utils.SPARQL import SPARQLUtils
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

# SPARQL string escapes (ECHAR): an argument stays inside the literal it fills.
_LITERAL_ESCAPES = str.maketrans(
    {"\\": "\\\\", '"': '\\"', "'": "\\'", "\n": "\\n", "\r": "\\r", "\t": "\\t"}
)


def _sparql_text(value: Any) -> Any:
    return value.translate(_LITERAL_ESCAPES) if isinstance(value, str) else value


@cache
def _templates() -> Any:
    """Templates render sandboxed: a template reaches its arguments, never Python."""
    from jinja2.sandbox import ImmutableSandboxedEnvironment

    return ImmutableSandboxedEnvironment(autoescape=False, finalize=_sparql_text)


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

    def run(self, parameters: T):
        try:
            template = _templates().from_string(self.sparql_template)
            sparql_query = template.render(**parameters.model_dump())
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
