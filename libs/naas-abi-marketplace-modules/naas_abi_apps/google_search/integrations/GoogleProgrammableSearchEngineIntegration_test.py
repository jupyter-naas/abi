"""Offline tests of the Google Search integration and the LinkedIn workflows."""

from __future__ import annotations

import asyncio

import httpx
from naas_abi_apps.common.testing import MemoryStorage
from naas_abi_apps.google_search.integrations.GoogleProgrammableSearchEngineIntegration import (
    GoogleProgrammableSearchEngineIntegration,
    GoogleProgrammableSearchEngineIntegrationConfiguration,
    page_text,
)
from naas_abi_apps.google_search.workflows.SearchLinkedInOrganizationPageWorkflow import (
    SearchLinkedInOrganizationPageWorkflow,
    SearchLinkedInOrganizationPageWorkflowConfiguration,
    SearchLinkedInOrganizationPageWorkflowParameters,
)
from naas_abi_apps.google_search.workflows.SearchLinkedInProfilePageWorkflow import (
    SearchLinkedInProfilePageWorkflow,
    SearchLinkedInProfilePageWorkflowConfiguration,
    SearchLinkedInProfilePageWorkflowParameters,
)


def configuration(
    handler, storage=None
) -> GoogleProgrammableSearchEngineIntegrationConfiguration:
    return GoogleProgrammableSearchEngineIntegrationConfiguration(
        api_key="k",
        search_engine_id="cx",
        storage=storage,
        transport=httpx.MockTransport(handler),
    )


def test_query_returns_every_page_up_to_num_results() -> None:
    starts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        starts.append(request.url.params["start"])
        start, num = int(request.url.params["start"]), int(request.url.params["num"])
        return httpx.Response(
            200,
            json={"items": [{"link": f"https://x/{start + i}"} for i in range(num)]},
        )

    storage = MemoryStorage()
    items = asyncio.run(
        GoogleProgrammableSearchEngineIntegration(
            configuration(handler, storage)
        ).query("abi docs", 15)
    )

    # The in-engine loop returned only the last page (5 items here).
    assert len(items) == 15 and items[0]["link"] == "https://x/1"
    assert starts == ["1", "11"]
    assert ("google_search/queries/abi_docs", "abi_docs.json") in storage.objects


def test_extract_content_keeps_visible_text_only() -> None:
    html = "<html><script>x()</script><body><h1>Title</h1>  <p>Body\n text</p></body></html>"

    def handler(request: httpx.Request) -> httpx.Response:
        assert "Mozilla" in request.headers["User-Agent"]
        return httpx.Response(200, text=html)

    text = asyncio.run(
        GoogleProgrammableSearchEngineIntegration(
            configuration(handler)
        ).extract_content("https://a.io/p")
    )

    assert text == "Title Body text" == page_text(html)


RESULTS = [
    {
        "title": "Ada - LinkedIn",
        "link": "https://fr.linkedin.com/in/ada-l?x=1",
        "snippet": "s1",
    },
    {"title": "Not a profile", "link": "https://example.com/ada", "snippet": "s2"},
    {
        "title": "Naas | LinkedIn",
        "link": "https://www.linkedin.com/company/naas-ai/",
        "snippet": "s3",
        "pagemap": {
            "metatags": [{"og:description": "AI"}],
            "cse_image": [{"src": "https://img"}],
        },
    },
]


def search_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"items": RESULTS})


def test_profile_workflow_keeps_profile_pages() -> None:
    storage = MemoryStorage()
    workflow = SearchLinkedInProfilePageWorkflow(
        SearchLinkedInProfilePageWorkflowConfiguration(
            integration=configuration(search_handler, storage)
        )
    )

    pages = asyncio.run(
        workflow.run(SearchLinkedInProfilePageWorkflowParameters(profile_name="Ada L"))
    )

    assert [p["link"] for p in pages] == ["https://fr.linkedin.com/in/ada-l?x=1"]
    assert (
        "google_search/linkedin_profile_pages/ada-l",
        "ada-l.json",
    ) in storage.objects


def test_organization_workflow_reads_the_page_metadata() -> None:
    storage = MemoryStorage()
    workflow = SearchLinkedInOrganizationPageWorkflow(
        SearchLinkedInOrganizationPageWorkflowConfiguration(
            integration=configuration(search_handler, storage)
        )
    )

    pages = asyncio.run(
        workflow.run(
            SearchLinkedInOrganizationPageWorkflowParameters(organization_name="Naas")
        )
    )

    assert pages == [
        {
            "title": "Naas | LinkedIn",
            "link": "https://www.linkedin.com/company/naas-ai/",
            "description": "AI",
            "cse_image": "https://img",
        }
    ]
    assert (
        "google_search/linkedin_company_pages/naas-ai",
        "naas-ai.json",
    ) in storage.objects
