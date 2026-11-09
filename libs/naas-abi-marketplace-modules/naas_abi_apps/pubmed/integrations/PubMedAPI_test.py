"""Offline tests of the PubMed client, pipeline and tools (no network)."""

from __future__ import annotations

import asyncio
import io

from naas_abi_apps.common.testing import MemoryStorage
from naas_abi_apps.pubmed.agents.PubMedAgent import build_tools
from naas_abi_apps.pubmed.integrations import PubMedAPI
from naas_abi_apps.pubmed.integrations.PubMedAPI import (
    PubMedAPIConfiguration,
    PubMedIntegration,
)
from naas_abi_apps.pubmed.pipelines.PubMedPipeline import (
    PubMedPipeline,
    PubMedPipelineConfiguration,
    PubMedPipelineParameters,
)


def doc(title: str, pmcid: str | None = None) -> dict:
    ids = [{"idtype": "pubmed", "value": "x"}]
    if pmcid:
        ids.append({"idtype": "pmc", "value": pmcid})
    return {
        "title": title,
        "fulljournalname": "Nature",
        "pubdate": "2024 Jan 2",
        "authors": [{"name": "Ada L"}],
        "articleids": ids,
    }


def test_summaries_are_cached_under_their_own_pmid(monkeypatch) -> None:
    monkeypatch.setattr(PubMedAPI, "cache", PubMedAPI._MemoryCache())
    integration = PubMedIntegration(PubMedAPIConfiguration())
    calls: list[str] = []

    def fake_request(endpoint, params, expect_json=True, method="GET", data=None):
        calls.append(data["id"])
        # PMID "2" has no document: the in-engine loop cached "3"'s summary as "2".
        return {"result": {"1": doc("One"), "3": doc("Three")}}

    monkeypatch.setattr(integration, "_make_request", fake_request)

    summaries = integration._summaries(["1", "2", "3"])

    assert [s.pubmedIdentifier for s in summaries] == ["1", "3"]
    assert [s.title for s in summaries] == ["One", "Three"]
    # Cached: a second call asks only for the PMID that had no document.
    integration._summaries(["1", "2", "3"])
    assert calls == ["1,2,3", "2"]


class FakeIntegration:
    def __init__(self) -> None:
        build = PubMedIntegration(PubMedAPIConfiguration())._build_summary
        self.summaries = [
            build("1", doc("Open", pmcid="PMC1")),
            build("2", doc("Closed")),
        ]
        self.searches: list[tuple] = []

    def search_date_range(self, query, **kwargs):
        self.searches.append((query, kwargs))
        return self.summaries

    def download_pubmed_central_pdf(self, pmcid: str):
        return io.BytesIO(f"%PDF {pmcid}".encode())


def test_the_pipeline_builds_the_graph_and_filters_downloadables() -> None:
    integration = FakeIntegration()
    pipeline = PubMedPipeline(PubMedPipelineConfiguration(), integration=integration)

    everything = asyncio.run(
        pipeline.run(PubMedPipelineParameters(query="crispr", start_date="2024-01-01"))
    )
    downloadable = asyncio.run(
        pipeline.run(
            PubMedPipelineParameters(
                query="crispr", start_date="2024-01-01", downloadable_only=True
            )
        )
    )

    assert len(downloadable) < len(everything)
    assert integration.searches[0] == (
        "crispr",
        {
            "start_date": "2024-01-01",
            "end_date": None,
            "sort": "pub_date",
            "max_results": 100,
        },
    )


def test_tools_return_turtle_and_store_pdfs() -> None:
    storage = MemoryStorage()
    pipeline = PubMedPipeline(
        PubMedPipelineConfiguration(), integration=FakeIntegration()
    )
    tools = {t.name: t for t in build_tools(pipeline, storage, "pubmed/pdfs")}

    turtle = asyncio.run(
        tools["search_downloadable_pubmed_papers"].ainvoke(
            {"query": "q", "start_date": "2024-01-01"}
        )
    )
    asyncio.run(tools["download_pdf"].ainvoke({"pmcids": ["PMC1", "PMC2"]}))

    assert "Open" in turtle
    assert storage.objects[("pubmed/pdfs", "PMC2.pdf")] == b"%PDF PMC2"


def test_a_pmcid_without_a_pdf_does_not_fail_the_others() -> None:
    class PartlyMissing(FakeIntegration):
        def download_pubmed_central_pdf(self, pmcid: str):
            if pmcid == "PMC404":
                raise FileNotFoundError("PubMed Central has no PDF for PMC404")
            return super().download_pubmed_central_pdf(pmcid)

    storage = MemoryStorage()
    pipeline = PubMedPipeline(
        PubMedPipelineConfiguration(), integration=PartlyMissing()
    )
    tools = {t.name: t for t in build_tools(pipeline, storage, "pubmed/pdfs")}

    report = asyncio.run(tools["download_pdf"].ainvoke({"pmcids": ["PMC404", "PMC2"]}))

    assert storage.objects == {("pubmed/pdfs", "PMC2.pdf"): b"%PDF PMC2"}
    assert "PMC404: not downloaded (PubMed Central has no PDF for PMC404)" in report
    assert "PMC2: saved as pubmed/pdfs/PMC2.pdf" in report
