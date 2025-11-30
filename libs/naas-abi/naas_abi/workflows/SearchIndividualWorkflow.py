from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Optional

from fastapi import APIRouter
from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.services.triple_store.TripleStorePorts import ITripleStoreService
from naas_abi_core.utils.String import normalize
from naas_abi_core.workflow import Workflow, WorkflowConfiguration
from naas_abi_core.workflow.workflow import WorkflowParameters
from pydantic import Field
from rdflib import query
from thefuzz import fuzz  # type: ignore


@dataclass
class SearchIndividualWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for SearchIndividual workflow."""

    triple_store: ITripleStoreService


class SearchIndividualWorkflowParameters(WorkflowParameters):
    """Parameters for SearchIndividual workflow."""

    search_label: Annotated[
        str,
        Field(
            ...,
            description="Individual label to search for in the ontology schema.",
            example="Naas.ai",
        ),
    ]
    class_uri: Optional[
        Annotated[
            str,
            Field(
                ...,
                description="Class URI to use to search for individuals.",
                example="https://www.commoncoreontologies.org/ont00000443",
            ),
        ]
    ] = None
    limit: Optional[
        Annotated[
            int,
            Field(
                description="Maximum number of results to return.",
                ge=1,
                le=100,
            ),
        ]
    ] = 10
    query: Optional[
        Annotated[
            str,
            Field(
                description="Custom SPARQL query to use to search for individuals.",
            ),
        ]
    ] = None


class SearchIndividualWorkflow(Workflow):
    """Workflow for searching ontology individuals."""

    __configuration: SearchIndividualWorkflowConfiguration

    def __init__(self, configuration: SearchIndividualWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def search_individual(
        self, parameters: SearchIndividualWorkflowParameters
    ) -> dict | list[dict]:
        class_uri_filter = (
            f"?individual_uri a <{parameters.class_uri}> ;"
            if parameters.class_uri
            else ""
        )
        search_label_norm = normalize(parameters.search_label)
        sparql_query = f"""
        SELECT DISTINCT ?individual_uri ?label
        WHERE {{
            # Ensure individual is a NamedIndividual
            ?individual_uri a owl:NamedIndividual .
            
            {class_uri_filter}

            {{
                # Search by rdfs:label
                ?individual_uri rdfs:label ?label .
                
                # Convert labels to lowercase for comparison
                BIND(LCASE(STR(?label)) AS ?lower_label)
                BIND(LCASE("{parameters.search_label}") AS ?lower_search)
                
                # Split search label into words and check if any word matches
                {{
                    # Full label match
                    FILTER(CONTAINS(?lower_label, ?lower_search) || CONTAINS(?lower_search, ?lower_label))
                }}
                UNION
                {{
                    # Word-by-word match
                    VALUES ?search_word {{ {" ".join([f'"{word.lower()}"' for word in parameters.search_label.split()])} }}
                    FILTER(CONTAINS(?lower_label, ?search_word))
                }}
            }}
            UNION
            {{
                # Search by skos:altLabel
                ?individual_uri skos:altLabel ?label .
                
                # Convert labels to lowercase for comparison
                BIND(LCASE(STR(?label)) AS ?lower_label)
                BIND(LCASE("{search_label_norm}") AS ?lower_search)
                
                # Split search label into words and check if any word matches
                {{
                    # Full label match
                    FILTER(CONTAINS(?lower_label, ?lower_search) || CONTAINS(?lower_search, ?lower_label))
                }}
                UNION
                {{
                    # Word-by-word match
                    VALUES ?search_word {{ {" ".join([f'"{word.lower()}"' for word in search_label_norm.split()])} }}
                    FILTER(CONTAINS(?lower_label, ?search_word))
                }}
            }}
        }}
        ORDER BY ?label
        LIMIT {parameters.limit}
        """
        if parameters.query is not None:
            sparql_query = parameters.query
        results = self.__configuration.triple_store.query(sparql_query)

        # Process results with fuzzy matching
        data = []
        for row in results:
            assert isinstance(row, query.ResultRow)
            data_dict = {}
            for key in row.labels:
                data_dict[key] = str(row[key]) if row[key] else None
                if key == "label" and row[key]:
                    score = fuzz.token_set_ratio(
                        search_label_norm, normalize(str(row[key]))
                    )
                    data_dict["score"] = score
            data.append(data_dict)

        # Sort by best match and remove duplicates
        if len(data) > 0:
            data.sort(
                key=lambda x: x["score"] if x["score"] is not None else 0, reverse=True
            )
            seen = set()
            unique_data = []
            for x in data:
                if x["individual_uri"] not in seen:
                    seen.add(x["individual_uri"])
                    unique_data.append(x)
            data = unique_data
        return data

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="search_individual",
                description="Search an ontology individual based on its label. It will return the most relevant individual using matching with rdfs:label",
                func=lambda **kwargs: self.search_individual(
                    SearchIndividualWorkflowParameters(**kwargs)
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
