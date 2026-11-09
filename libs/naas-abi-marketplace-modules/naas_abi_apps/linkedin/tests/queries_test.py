"""The connection templates and the name search, on a graph the people module's
connections pipeline built (``connections.ttl``)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from naas_abi_apps.common.sparql_templates import module_queries, query_tools
from naas_abi_apps.common.testing import FakeTripleStore, FakeVectorStore
from naas_abi_apps.linkedin.workflows.CreateClassEmbeddingsWorkflow import (
    CreateClassEmbeddingsWorkflow,
    CreateClassEmbeddingsWorkflowConfiguration,
    CreateClassEmbeddingsWorkflowParameters,
    search_tools,
)

PACKAGE = Path(__file__).parents[1]
ALICE = "http://ontology.naas.ai/abi/Person#00000000-0000-4000-8000-000000000001"
JANE = "http://ontology.naas.ai/abi/Person/linkedin-jane-doe"
AXA = "http://ontology.naas.ai/abi/Organization/axa"


class LetterEmbeddings:
    """Names that share letters are close: enough to rank a search."""

    @staticmethod
    def vector(text: str) -> list[float]:
        return [float(text.lower().count(c)) for c in "abcdefghijklmnopqrstuvwxyz"]

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.vector(t) for t in texts]

    async def aembed_query(self, text: str) -> list[float]:
        return self.vector(text)


@pytest.fixture
def store() -> FakeTripleStore:
    store = FakeTripleStore()
    store.dataset.graph("http://ontology.naas.ai/graph/user-alice/linkedin").parse(
        Path(__file__).with_name("connections.ttl")
    )
    return store


@pytest.fixture
def tools(store) -> dict:
    return {t.name: t for t in query_tools(module_queries(PACKAGE), store)}


def call(tool, **arguments):
    return asyncio.run(tool.coroutine(**arguments))


def test_count_connections(tools) -> None:
    assert call(tools["linkedin_count_connections_by_person"], person_uri=ALICE) == [
        {"connectionCount": "2"}
    ]
    # The connection is mutual: Jane has one, Alice.
    assert call(tools["linkedin_count_connections_by_person"], person_uri=JANE) == [
        {"connectionCount": "1"}
    ]


def test_search_connections_by_person(tools) -> None:
    rows = call(tools["linkedin_search_connections_by_person"], person_uri=ALICE)
    assert [r["connectedPersonName"] for r in rows] == ["Jane Doe", "John Smith"]
    jane = rows[0]
    assert jane["connectedOn"] == "2025-10-23"
    assert (jane["jobTitles"], jane["organizations"]) == ("Chief Risk Officer", "AXA")
    assert jane["linkedinUrl"] == "https://www.linkedin.com/in/jane-doe"
    assert jane["emailAddress"] == "jane@example.org"


def test_search_connections_by_organization(tools) -> None:
    rows = call(
        tools["linkedin_search_connections_by_organization"], organization_uri=AXA
    )
    assert [(r["personName"], r["ownerName"]) for r in rows] == [
        ("Jane Doe", "Alice Martin")
    ]


def test_search_person_info(tools) -> None:
    [row] = call(tools["linkedin_search_person_info"], person_uri=JANE)
    assert row["name"] == "Jane Doe"
    assert row["headline"] == "Chief Risk Officer"
    assert row["organizations"] == "AXA"


@pytest.mark.parametrize(
    "uri",
    [
        f"{JANE}> . ?s ?p ?o . <x",
        "http://example.org/Person/1",
        f"{JANE} ",
    ],
)
def test_an_argument_cannot_leave_its_iri(tools, uri) -> None:
    [row] = call(tools["linkedin_search_person_info"], person_uri=uri)
    assert "error" in row


def test_embeddings_are_added_once_then_searched(store) -> None:
    vectors = FakeVectorStore()
    embeddings = LetterEmbeddings()
    workflow = CreateClassEmbeddingsWorkflow(
        CreateClassEmbeddingsWorkflowConfiguration(
            triple_store=store, vector_store=vectors, embeddings=embeddings
        )
    )
    first = asyncio.run(workflow.run(CreateClassEmbeddingsWorkflowParameters()))
    again = asyncio.run(workflow.run(CreateClassEmbeddingsWorkflowParameters()))

    assert [(r["entities"], r["embedded"]) for r in first] == [(3, 3), (2, 2)]
    assert [r["embedded"] for r in again] == [0, 0]

    person, company = search_tools(vectors, embeddings)
    best = call(person, person_name="jane doe", k=1)
    assert best[0]["uri"] == JANE
    assert call(company, company_name="AXA", k=1)[0]["uri"] == AXA


def test_an_unknown_collection_is_refused(store) -> None:
    workflow = CreateClassEmbeddingsWorkflow(
        CreateClassEmbeddingsWorkflowConfiguration(
            triple_store=store,
            vector_store=FakeVectorStore(),
            embeddings=LetterEmbeddings(),
        )
    )
    with pytest.raises(ValueError, match="Unknown collections"):
        asyncio.run(
            workflow.run(CreateClassEmbeddingsWorkflowParameters(collections=["x"]))
        )
