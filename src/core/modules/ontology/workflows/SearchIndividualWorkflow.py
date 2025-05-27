from abi.workflow import Workflow, WorkflowConfiguration
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from dataclasses import dataclass
from pydantic import Field
from abi.workflow.workflow import WorkflowParameters
from fastapi import APIRouter
from langchain_core.tools import StructuredTool, BaseTool
from abi.utils.SPARQL import results_to_list
from typing import Annotated, List, Dict, Optional
from enum import Enum

@dataclass
class SearchIndividualWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for SearchIndividual workflow."""

    triple_store: ITripleStoreService


class SearchIndividualWorkflowParameters(WorkflowParameters):
    """Parameters for SearchIndividual workflow."""
    search_label: Annotated[str, Field(
        ...,
        description="Individual label to search for in the ontology schema.",
        example="Naas.ai",
    )]
    class_uri: Optional[Annotated[str, Field(
        ...,
        description="Class URI to use to search for individuals.",
        pattern="https?:\/\/.*",
        example="https://www.commoncoreontologies.org/ont00000443",
    )]] = None


class SearchIndividualWorkflow(Workflow):
    """Workflow for searching ontology individuals."""

    __configuration: SearchIndividualWorkflowConfiguration

    def __init__(self, configuration: SearchIndividualWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def search_individual(self, parameters: SearchIndividualWorkflowParameters) -> List[Dict]:
        # Base query without class filter
        query = f"""
        SELECT DISTINCT ?class_uri ?individual_uri ?label (MAX(?temp_score) AS ?score)
        WHERE {{
            # Ensure individual is a NamedIndividual
            ?individual_uri a ?class_uri ;
                            a owl:NamedIndividual ;
                            rdfs:label ?label .
            
            # Add class filter if class_uri is provided
            {f'FILTER(?class_uri = <{parameters.class_uri}>)' if parameters.class_uri else ''}
            
            # Calculate scores for perfect and partial matches
            BIND(IF(LCASE(STR(?label)) = LCASE("{parameters.search_label}"), 10, 0) AS ?perfect_score)
            BIND(IF(CONTAINS(LCASE(STR(?label)), LCASE("{parameters.search_label}")), 8, 0) AS ?partial_score)
            
            # Use the higher of the two scores
            BIND(IF(?perfect_score > ?partial_score, ?perfect_score, ?partial_score) AS ?temp_score)
            
            # Only include results with a score > 0
            FILTER(?temp_score > 0)
        }}
        GROUP BY ?class_uri ?individual_uri ?label
        ORDER BY DESC(?score) ?label
        """
        results = self.__configuration.triple_store.query(query)
        return results_to_list(results)

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="search_individual",
                description="Search an ontology individual based on its label. It will return the most relevant individual using matching with rdfs:label",
                func=lambda class_uri, search_label: self.search_individual(
                    SearchIndividualWorkflowParameters(
                        class_uri=class_uri, search_label=search_label
                    )
                ),
                args_schema=SearchIndividualWorkflowParameters,
            )
        ]

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        if tags is None:
            tags = []
        return None

