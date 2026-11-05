"""Offline: a Sanax Excel export in object storage, imported into a fake triple
store, then queried with the module's SPARQL template tools."""

from __future__ import annotations

import asyncio
import io

import pandas as pd
from naas_abi_apps.common.testing import FakeTripleStore, MemoryStorage
from naas_abi_apps.sanax.agents.SanaxAgent import build_tools
from naas_abi_apps.sanax.pipelines.SanaxLinkedInSalesNavigatorExtractorPipeline import (
    SanaxLinkedInSalesNavigatorExtractorPipeline,
    SanaxLinkedInSalesNavigatorExtractorPipelineConfiguration,
    SanaxLinkedInSalesNavigatorExtractorPipelineParameters,
)

GRAPH = "http://ontology.naas.ai/graph/default"
ROWS = [
    {
        "Name": "John Smith",
        "Job Title": "Executive Partner",
        "Company": "",
        "Company URL": "",
        "Location": "New York, United States",
        "Time in Role": "1 year 1 month in role",
        "Time in Company": "1 year 1 month in company",
        "LinkedIn URL": "https://www.linkedin.com/sales/lead/john",
    },
    {
        "Name": "Jane Doe",
        "Job Title": "CEO",
        "Company": "Tech Solutions",
        "Company URL": "https://www.linkedin.com/company/techsolutions",
        "Location": "London, United Kingdom",
        "Time in Role": "3 years 6 months in role",
        "Time in Company": "5 years in company",
        "LinkedIn URL": "https://www.linkedin.com/sales/lead/jane",
    },
]


def setup() -> tuple[
    SanaxLinkedInSalesNavigatorExtractorPipeline, FakeTripleStore, MemoryStorage
]:
    storage, store = MemoryStorage(), FakeTripleStore()
    excel = io.BytesIO()
    pd.DataFrame(ROWS).to_excel(
        excel, index=False, sheet_name="LinkedIn Sales Navigator"
    )
    storage.objects[("sanax/exports", "leads.xlsx")] = excel.getvalue()
    pipeline = SanaxLinkedInSalesNavigatorExtractorPipeline(
        SanaxLinkedInSalesNavigatorExtractorPipelineConfiguration(
            triple_store=store, storage=storage
        )
    )
    return pipeline, store, storage


def test_the_export_is_imported_and_logged() -> None:
    pipeline, store, storage = setup()

    graph = asyncio.run(
        pipeline.run(
            SanaxLinkedInSalesNavigatorExtractorPipelineParameters(
                file_path="sanax/exports/leads.xlsx"
            )
        )
    )

    assert len(graph) > 0 and store.inserts == [(GRAPH, len(graph))]
    written = {key for (_, key) in storage.objects}
    assert {
        "insert_leads_LinkedIn Sales Navigator.ttl",
        "leads_LinkedIn Sales Navigator.xlsx",
    } <= written


def test_a_missing_file_gives_an_empty_graph() -> None:
    pipeline, store, _ = setup()

    graph = asyncio.run(
        pipeline.run(
            SanaxLinkedInSalesNavigatorExtractorPipelineParameters(
                file_path="sanax/exports/none.xlsx"
            )
        )
    )

    assert len(graph) == 0 and store.inserts == []


def test_template_tools_query_the_imported_people() -> None:
    pipeline, store, _ = setup()
    asyncio.run(
        pipeline.run(
            SanaxLinkedInSalesNavigatorExtractorPipelineParameters(
                file_path="sanax/exports/leads.xlsx"
            )
        )
    )
    tools = {t.name: t for t in build_tools(store)}

    found = asyncio.run(
        tools["sanax_search_persons_by_name"].ainvoke({"search_term": "jane"})
    )
    counted = asyncio.run(
        tools["count_items"].ainvoke(
            {
                "function_name": "sanax_search_persons_by_name",
                "function_args": {"search_term": "o"},
            }
        )
    )

    assert [row["personName"] for row in found] == ["Jane Doe"]
    assert counted == 2
    # Defined in the TTL, but asked for under another name by the in-engine agent.
    assert "sanax_get_people_with_longest_job_starts" in tools
