from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, cast

import numpy as np
from langchain_core.tools import BaseTool, StructuredTool
from langchain_openai import OpenAIEmbeddings
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.triple_store.TripleStorePorts import ITripleStoreService
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_core.workflow import Workflow, WorkflowConfiguration
from naas_abi_core.workflow.workflow import WorkflowParameters
from pydantic import Field, SecretStr
from rdflib.query import ResultRow

DEFAULT_COLLECTION_NAME = "locations"
DEFAULT_MODEL_ID = "text-embedding-3-small"
DEFAULT_DIMENSION = 1536

_INDIVIDUALS_QUERY = """
PREFIX abi: <http://ontology.naas.ai/abi/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX bfo: <http://purl.obolibrary.org/obo/>
PREFIX cco: <https://www.commoncoreontologies.org/>

SELECT ?individual ?type ?label
       ?parentLabel1 ?parentLabel2 ?parentLabel3 ?parentLabel4
       ?countryCode ?stateCode ?regionCode ?latitude ?longitude
WHERE {
    GRAPH ?g {
        ?individual a ?type ;
                    rdfs:label ?label .
        FILTER(?type IN (abi:Country, abi:State, abi:Region, abi:City, abi:PostalCode))

        OPTIONAL { ?individual bfo:BFO_0000171 ?parent1 . ?parent1 rdfs:label ?parentLabel1 .
        OPTIONAL { ?parent1 bfo:BFO_0000171 ?parent2 . ?parent2 rdfs:label ?parentLabel2 .
        OPTIONAL { ?parent2 bfo:BFO_0000171 ?parent3 . ?parent3 rdfs:label ?parentLabel3 .
        OPTIONAL { ?parent3 bfo:BFO_0000171 ?parent4 . ?parent4 rdfs:label ?parentLabel4 . } } } }

        OPTIONAL { ?individual abi:country_code ?countryCode }
        OPTIONAL { ?individual abi:state_code ?stateCode }
        OPTIONAL { ?individual abi:region_code ?regionCode }
        OPTIONAL { ?individual cco:ont00001766 ?latitude }
        OPTIONAL { ?individual cco:ont00001764 ?longitude }
    }
}
"""


@dataclass
class LocationsWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for LocationsWorkflow.

    Attributes:
        triple_store: Triple store service to read location individuals from.
        vector_store: Vector store service to write/search embeddings in.
        secret: Secret service used to fetch the OpenAI API key (OPENAI_API_KEY).
        collection_name: Vector store collection populated by `run()` and queried by `search()`.
        model_id: OpenAI embedding model to use.
        dimension: Embedding dimension matching `model_id`.
        batch_size: Number of individuals embedded per API call.
    """

    triple_store: ITripleStoreService
    vector_store: VectorStoreService
    secret: Secret
    collection_name: str = DEFAULT_COLLECTION_NAME
    model_id: str = DEFAULT_MODEL_ID
    dimension: int = DEFAULT_DIMENSION
    batch_size: int = 100


class LocationsWorkflowParameters(WorkflowParameters):
    """Parameters for vectorizing all locations (no arguments needed)."""

    pass


class LocationsSearchParameters(WorkflowParameters):
    """Parameters for semantic search over vectorized locations."""

    query: str = Field(
        ..., description="Free-text location description to match, e.g. 'Paris France' or '75001'."
    )
    k: int = Field(5, description="Number of matches to return.")


class LocationsWorkflow(Workflow[LocationsWorkflowParameters]):
    """Embeds every Country/State/Region/City/PostalCode individual from the triple
    store into a single vector store collection, and exposes semantic search over it
    so a free-text location description can be matched to the closest indexed location.
    """

    __configuration: LocationsWorkflowConfiguration

    def __init__(self, configuration: LocationsWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def __embeddings_model(self) -> OpenAIEmbeddings:
        api_key = self.__configuration.secret.get("OPENAI_API_KEY")
        return OpenAIEmbeddings(
            model=self.__configuration.model_id,
            dimensions=self.__configuration.dimension,
            api_key=SecretStr(api_key),
        )

    def __fetch_individuals(self) -> List[Dict[str, Any]]:
        results = self.__configuration.triple_store.query(_INDIVIDUALS_QUERY)
        records = []
        for row in results:
            row = cast(ResultRow, row)
            parents = [
                str(label)
                for label in (row.parentLabel1, row.parentLabel2, row.parentLabel3, row.parentLabel4)
                if label is not None
            ]
            records.append(
                {
                    "uri": str(row.individual),
                    "type": str(row.type).rsplit("/", 1)[-1],
                    "label": str(row.label),
                    "parents": parents,
                    "country_code": str(row.countryCode) if row.countryCode is not None else None,
                    "state_code": str(row.stateCode) if row.stateCode is not None else None,
                    "region_code": str(row.regionCode) if row.regionCode is not None else None,
                    "latitude": float(row.latitude) if row.latitude is not None else None,
                    "longitude": float(row.longitude) if row.longitude is not None else None,
                }
            )
        return records

    @staticmethod
    def __build_text(record: Dict[str, Any]) -> str:
        return ", ".join([record["label"], *record["parents"]])

    def run(self, parameters: LocationsWorkflowParameters) -> dict:
        """Vectorize every location individual into `collection_name`.

        Returns:
            dict with `collection_name` and the number of individuals embedded.
        """
        cfg = self.__configuration
        records = self.__fetch_individuals()
        if not records:
            return {"collection_name": cfg.collection_name, "count": 0}

        embeddings_model = self.__embeddings_model()
        cfg.vector_store.ensure_collection(
            collection_name=cfg.collection_name,
            dimension=cfg.dimension,
            distance_metric="cosine",
        )

        total = 0
        for i in range(0, len(records), cfg.batch_size):
            batch = records[i : i + cfg.batch_size]
            texts = [self.__build_text(r) for r in batch]
            vectors = embeddings_model.embed_documents(texts)
            cfg.vector_store.add_documents(
                collection_name=cfg.collection_name,
                ids=[r["uri"] for r in batch],
                vectors=[np.array(v) for v in vectors],
                metadata=[
                    {
                        "uri": r["uri"],
                        "type": r["type"],
                        "label": r["label"],
                        "text": texts[j],
                        "country_code": r["country_code"],
                        "state_code": r["state_code"],
                        "region_code": r["region_code"],
                        "latitude": r["latitude"],
                        "longitude": r["longitude"],
                    }
                    for j, r in enumerate(batch)
                ],
            )
            total += len(batch)

        return {"collection_name": cfg.collection_name, "count": total}

    def search(self, parameters: LocationsSearchParameters) -> List[dict]:
        """Find the closest indexed locations to a free-text query.

        Returns:
            List of matches ordered by similarity, each with the location's `uri`,
            `score`, and the metadata stored by `run()`.
        """
        cfg = self.__configuration
        embeddings_model = self.__embeddings_model()
        query_vector = np.array(embeddings_model.embed_query(parameters.query))
        results = cfg.vector_store.search_similar(
            collection_name=cfg.collection_name,
            query_vector=query_vector,
            k=parameters.k,
        )
        return [{"uri": r.id, "score": r.score, **(r.metadata or {})} for r in results]

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="vectorize_locations",
                description="Embed every location (Country/State/Region/City/PostalCode) from the "
                "knowledge graph into the locations vector collection",
                func=lambda **kwargs: self.run(LocationsWorkflowParameters(**kwargs)),
                args_schema=LocationsWorkflowParameters,
            ),
            StructuredTool(
                name="search_locations",
                description="Semantic search over vectorized locations to find the closest match "
                "to a free-text location description",
                func=lambda **kwargs: self.search(LocationsSearchParameters(**kwargs)),
                args_schema=LocationsSearchParameters,
            ),
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
