"""Offline tests of the ArXiv integration, pipeline and queries."""

from __future__ import annotations

import asyncio
import threading
from datetime import UTC, datetime
from types import SimpleNamespace

from naas_abi_apps.arxiv.integrations.ArXivIntegration import (
    ArXivIntegration,
    ArXivIntegrationConfiguration,
)
from naas_abi_apps.arxiv.pipelines.ArXivPaperPipeline import (
    ArXivPaperPipeline,
    ArXivPaperPipelineConfiguration,
    ArXivPaperPipelineParameters,
)
from naas_abi_apps.arxiv.queries import ArXivQueries
from naas_abi_apps.common.testing import FakeTripleStore, MemoryStorage

GRAPH = "http://ontology.naas.ai/graph/arxiv"


def fake_paper(
    paper_id: str, title: str, authors: list[str], categories: list[str]
) -> SimpleNamespace:
    return SimpleNamespace(
        entry_id=f"http://arxiv.org/abs/{paper_id}",
        title=title,
        authors=authors,
        summary=f"About {title}",
        published=datetime(2024, 1, 2, tzinfo=UTC),
        updated=None,
        categories=categories,
        links=[SimpleNamespace(href=f"http://arxiv.org/abs/{paper_id}")],
        pdf_url=f"http://arxiv.org/pdf/{paper_id}",
    )


PAPERS = {
    "2401.00001v1": fake_paper(
        "2401.00001v1", 'Attention "Again"', ["Ada Lovelace", "Alan Turing"], ["cs.LG"]
    ),
    "2401.00002v1": fake_paper("2401.00002v1", "Graphs", ["Ada Lovelace"], ["cs.AI"]),
}


class FakeArxiv:
    searches: list[dict] = []

    class Search:
        def __init__(self, **kwargs) -> None:
            FakeArxiv.searches.append(kwargs)
            self.kwargs = kwargs

    class Client:
        def results(self, search):
            assert threading.current_thread() is not threading.main_thread()
            ids = search.kwargs.get("id_list")
            return iter([PAPERS[i] for i in ids] if ids else list(PAPERS.values()))


def configuration() -> ArXivIntegrationConfiguration:
    return ArXivIntegrationConfiguration(library=lambda: FakeArxiv)


def test_search_returns_json_records_off_the_loop() -> None:
    papers = asyncio.run(ArXivIntegration(configuration()).search_papers("attention"))

    assert [p["id"] for p in papers] == ["2401.00001v1", "2401.00002v1"]
    assert papers[0]["published"] == "2024-01-02T00:00:00+00:00"
    assert FakeArxiv.searches[-1] == {"query": "attention", "max_results": 10}


def pipeline(store: FakeTripleStore, storage: MemoryStorage) -> ArXivPaperPipeline:
    async def download(url: str) -> bytes:
        return b"%PDF " + url.encode()

    return ArXivPaperPipeline(
        ArXivPaperPipelineConfiguration(
            triple_store=store,
            storage=storage,
            integration=configuration(),
            download=download,
        )
    )


def test_the_pipeline_writes_the_paper_to_the_graph_and_the_pdf_to_storage() -> None:
    store, storage = FakeTripleStore(), MemoryStorage()

    graph = asyncio.run(
        pipeline(store, storage).run(
            ArXivPaperPipelineParameters(paper_id="2401.00001v1")
        )
    )

    assert store.inserts == [(GRAPH, len(graph))]
    ((prefix, key),) = storage.objects
    assert prefix == "arxiv/papers" and key == "attention_again_2401.00001v1.pdf"


def test_queries_run_against_the_module_graph() -> None:
    store = FakeTripleStore()
    run = pipeline(store, MemoryStorage()).run
    for paper_id in PAPERS:
        asyncio.run(
            run(ArXivPaperPipelineParameters(paper_id=paper_id, download_pdf=False))
        )
    queries = ArXivQueries(store, GRAPH)

    authors = asyncio.run(queries.query_authors(paper_title='attention "again'))
    assert sorted(authors["papers"][0]["authors"]) == ["Ada Lovelace", "Alan Turing"]
    by_category = asyncio.run(queries.query_papers(category="cs.ai"))
    assert [p["title"] for p in by_category["papers"]] == ["Graphs"]
    frequent = asyncio.run(queries.frequent_authors())
    assert frequent["authors"][0] == {"name": "Ada Lovelace", "paper_count": 2}
    assert "ArXivPaper" in queries.schema()["schema"]
    assert "error" in asyncio.run(queries.query_papers())
    assert "error" in asyncio.run(queries.execute("NOT SPARQL"))


def test_user_input_cannot_break_out_of_the_filter() -> None:
    store = FakeTripleStore()
    asyncio.run(
        pipeline(store, MemoryStorage()).run(
            ArXivPaperPipelineParameters(paper_id="2401.00002v1", download_pdf=False)
        )
    )

    result = asyncio.run(
        ArXivQueries(store, GRAPH).query_papers(
            author_name='x")) } ?s ?p ?o . FILTER(("'
        )
    )

    assert result == {"papers": []}
