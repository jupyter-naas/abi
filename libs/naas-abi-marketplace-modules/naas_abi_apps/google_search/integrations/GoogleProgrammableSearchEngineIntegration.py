"""Google Programmable Search Engine and page text extraction, async, on
``naas_abi_sdk`` only.

Port of ``naas_abi_marketplace.applications.google_search.integrations``:
same tool names. ``query`` now returns every page it fetched (the in-engine
loop kept only the last page); a page that fails after the first ends the
search with the results so far, as the in-engine loop stopped. Results are
archived to object storage.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Any

from naas_abi_apps.common.http import HttpConfiguration, request
from naas_abi_apps.common.storage import ObjectStorage, archive_json
from naas_abi_sdk.integration import Integration, IntegrationConnectionError

logger = logging.getLogger(__name__)

SERVICE = "Google Search"
BROWSER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
)
PAGE_SIZE = 10  # the API's maximum per request
MAX_RESULTS = 100  # the API serves no result past the 100th


def clean(value: str) -> str:
    """A storage-safe name: word characters, spaces as underscores."""
    return re.sub(r"[^\w\s|]", "", value).strip().replace(" ", "_")


def page_text(html: str) -> str:
    """Visible text of an HTML page, whitespace collapsed."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return " ".join(soup.get_text(separator=" ", strip=True).split())


@dataclass
class GoogleProgrammableSearchEngineIntegrationConfiguration(HttpConfiguration):
    api_key: str
    search_engine_id: str
    base_url: str = "https://www.googleapis.com/customsearch/v1"
    datastore_path: str = "google_search"
    storage: ObjectStorage | None = None


class GoogleProgrammableSearchEngineIntegration(Integration):
    """Web search and page content extraction."""

    def __init__(
        self, configuration: GoogleProgrammableSearchEngineIntegrationConfiguration
    ):
        super().__init__(configuration)
        self.configuration = configuration

    async def query(self, query: str, num_results: int = 5) -> list[dict[str, Any]]:
        """Up to ``num_results`` results (title, link, snippet, pagemap), paging
        by 10, at most 100 (the API's limit). A failure on the first page
        raises; on a later one, the results so far are returned."""
        num_results = max(0, min(num_results, MAX_RESULTS))
        items: list[dict[str, Any]] = []
        start = 1
        while len(items) < num_results:
            count = min(PAGE_SIZE, num_results - len(items))
            try:
                response = await request(
                    self.configuration,
                    "GET",
                    self.configuration.base_url,
                    service=SERVICE,
                    params={
                        "key": self.configuration.api_key,
                        "cx": self.configuration.search_engine_id,
                        "q": query,
                        "num": count,
                        "start": start,
                    },
                )
            except IntegrationConnectionError as exc:
                if not items:
                    raise
                logger.warning(
                    "Google Search: stopped after %d results: %s", len(items), exc
                )
                break
            page = response.json().get("items", [])
            items.extend(page)
            start += len(page)
            if len(page) < count:
                break
        name = clean(query)
        await archive_json(
            self.configuration.storage,
            f"{self.configuration.datastore_path}/queries/{name}",
            f"{name}.json",
            items,
        )
        return items

    async def extract_content(self, url: str) -> str:
        """Text content of a web page."""
        response = await request(
            self.configuration,
            "GET",
            url,
            service=SERVICE,
            headers={"User-Agent": BROWSER_AGENT},
        )
        text = await asyncio.to_thread(page_text, response.text)
        if self.configuration.storage is not None:
            name = clean(url)
            await self.configuration.storage.put_object(
                f"{self.configuration.datastore_path}/extracted_content/{name}",
                f"{name}.txt",
                text.encode("utf-8"),
            )
        return text


def as_tools(
    configuration: GoogleProgrammableSearchEngineIntegrationConfiguration,
) -> list[Any]:
    """LangChain tools over the integration."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = GoogleProgrammableSearchEngineIntegration(configuration)

    class SearchSchema(BaseModel):
        query: str = Field(..., description="Search query")
        num_results: int = Field(
            5, description="Number of results to return (at most 100)"
        )

    class ExtractContentSchema(BaseModel):
        url: str = Field(..., description="URL to extract content from")

    async def search(query: str, num_results: int = 5) -> Any:
        return await integration.query(query, num_results)

    async def extract(url: str) -> Any:
        return await integration.extract_content(url)

    return [
        StructuredTool(
            name="googlesearch_query",
            description="Search the web using Google Programmable Search Engine",
            coroutine=search,
            args_schema=SearchSchema,
        ),
        StructuredTool(
            name="googlesearch_extract_content_from_url",
            description="Extract text content from a web page URL using BeautifulSoup",
            coroutine=extract,
            args_schema=ExtractContentSchema,
        ),
    ]
