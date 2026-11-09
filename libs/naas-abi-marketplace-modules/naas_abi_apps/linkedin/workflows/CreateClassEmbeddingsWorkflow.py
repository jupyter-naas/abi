"""Embed the names of the people and organizations of the knowledge graph, for
the KG agent's ``linkedin_search_person_uri`` / ``linkedin_search_company_uri``
(``workflow.create_class_embeddings_workflow``).

Port of the in-engine workflow, which ran at every engine load. Changed:
- it embeds with the engine's embedding model (``embedding_model``, empty: the
  default), the one the search tools embed the question with. In-engine it
  embedded with a hard-coded OpenAI model and searched with the engine's
  default, which only matched when the two were the same;
- it reads ``abi:Person`` / ``abi:Organization`` (what the people module
  writes) as well as ``cco:ont00001262`` / ``cco:ont00001180`` (all it read);
- document ids are a UUID of the IRI (Qdrant refuses ``Person#<uuid>``), and
  the ids already in a collection are listed once, not fetched one by one.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from naas_abi_apps.common.sparql_templates import results_to_list
from naas_abi_sdk.workflow import Workflow, WorkflowConfiguration, WorkflowParameters
from pydantic import Field

logger = logging.getLogger(__name__)

PERSONS = "linkedin_persons"
COMPANIES = "linkedin_companies"
# Collection -> the classes whose individuals it holds.
COLLECTIONS: dict[str, tuple[str, ...]] = {
    PERSONS: (
        "http://ontology.naas.ai/abi/Person",
        "https://www.commoncoreontologies.org/ont00001262",
    ),
    COMPANIES: (
        "http://ontology.naas.ai/abi/Organization",
        "https://www.commoncoreontologies.org/ont00001180",
    ),
}
BATCH = 256


def document_id(uri: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, uri))


def labelled_individuals_query(classes: tuple[str, ...]) -> str:
    values = " ".join(f"<{c}>" for c in classes)
    return f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?entity (SAMPLE(?name) AS ?label)
        WHERE {{
          VALUES ?class {{ {values} }}
          ?entity a ?class ;
                  rdfs:label ?name .
        }}
        GROUP BY ?entity
    """


@dataclass
class CreateClassEmbeddingsWorkflowConfiguration(WorkflowConfiguration):
    """triple_store, vector_store: the engine's services. embeddings: an object
    with ``aembed_documents`` (the engine's embedding model)."""

    triple_store: Any = None
    vector_store: Any = None
    embeddings: Any = field(default=None, repr=False)


class CreateClassEmbeddingsWorkflowParameters(WorkflowParameters):
    collections: list[str] = Field(
        default_factory=lambda: list(COLLECTIONS),
        description=f"Collections to bring up to date, among {sorted(COLLECTIONS)}",
    )


class CreateClassEmbeddingsWorkflow(Workflow[CreateClassEmbeddingsWorkflowParameters]):
    """Embeds the names of the people and organizations of the knowledge graph
    that are not in their vector collection yet."""

    def __init__(self, configuration: CreateClassEmbeddingsWorkflowConfiguration):
        super().__init__(configuration)
        self.configuration = configuration

    async def _existing_ids(self, collection: str) -> set[str]:
        store = self.configuration.vector_store
        ids: set[str] = set()
        cursor = None
        while True:
            page = await store.list_documents(collection, limit=1000, cursor=cursor)
            ids.update(d.id for d in page.documents)
            cursor = page.next_cursor
            if not cursor:
                return ids

    async def _update(self, collection: str) -> dict[str, Any]:
        c = self.configuration
        rows = (
            results_to_list(
                await c.triple_store.query(
                    labelled_individuals_query(COLLECTIONS[collection])
                )
            )
            or []
        )
        entities = {
            row["entity"]: row["label"]
            for row in rows
            if row.get("entity") and row.get("label")
        }
        if not entities:
            return {"collection": collection, "entities": 0, "embedded": 0}
        if collection in await c.vector_store.list_collections():
            existing = await self._existing_ids(collection)
            new = [
                (u, label)
                for u, label in entities.items()
                if document_id(u) not in existing
            ]
        else:
            new = list(entities.items())
        embedded = 0
        for i in range(0, len(new), BATCH):
            batch = new[i : i + BATCH]
            vectors = await c.embeddings.aembed_documents([label for _, label in batch])
            if i == 0:
                await c.vector_store.ensure_collection(
                    collection, dimension=len(vectors[0]), distance_metric="cosine"
                )
            await c.vector_store.add_documents(
                collection,
                ids=[document_id(u) for u, _ in batch],
                vectors=vectors,
                metadata=[{"uri": u, "label": label} for u, label in batch],
            )
            embedded += len(batch)
        logger.info("%s: %d of %d embedded", collection, embedded, len(entities))
        return {
            "collection": collection,
            "entities": len(entities),
            "embedded": embedded,
        }

    async def run(
        self, parameters: CreateClassEmbeddingsWorkflowParameters
    ) -> list[dict[str, Any]]:
        unknown = sorted(set(parameters.collections) - set(COLLECTIONS))
        if unknown:
            raise ValueError(
                f"Unknown collections {unknown}; known: {sorted(COLLECTIONS)}"
            )
        return [await self._update(name) for name in parameters.collections]


def search_tools(vector_store: Any, embeddings: Any) -> list[Any]:
    """``linkedin_search_person_uri`` and ``linkedin_search_company_uri``: the
    closest names in the two collections."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel

    def make(collection: str, parameter: str, label: str) -> Any:
        schema = type(
            f"Search{label.capitalize()}Schema",
            (BaseModel,),
            {
                "__annotations__": {parameter: str, "k": int},
                parameter: Field(
                    ..., description=f"The name of the {label} to search for"
                ),
                "k": Field(10, ge=1, le=20, description="Number of results to return"),
            },
        )

        async def search(**arguments: Any) -> list[dict[str, Any]]:
            values = schema(**arguments)
            try:
                vector = await embeddings.aembed_query(getattr(values, parameter))
                results = await vector_store.search_similar(
                    collection, vector, k=values.k, include_metadata=True
                )
            except Exception as exc:  # noqa: BLE001 - reported to the agent
                return [
                    {
                        "error": f"{exc!s} (run workflow.create_class_embeddings_workflow)"
                    }
                ]
            return [
                {
                    "uri": r.metadata.get("uri", ""),
                    "label": r.metadata.get("label", ""),
                    "score": float(r.score),
                }
                for r in results
                if r.metadata
            ]

        return StructuredTool(
            name=f"linkedin_search_{'person' if label == 'person' else 'company'}_uri",
            description=(
                f"Search for {label} URIs in the knowledge graph by name, using "
                f"semantic similarity. Use it to find the URI of a {label} by name."
            ),
            coroutine=search,
            args_schema=schema,
        )

    return [
        make(PERSONS, "person_name", "person"),
        make(COMPANIES, "company_name", "company"),
    ]
