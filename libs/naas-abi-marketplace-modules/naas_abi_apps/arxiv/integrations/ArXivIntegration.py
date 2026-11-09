"""ArXiv API (the ``arxiv`` library), on ``naas_abi_sdk`` only.

Port of ``naas_abi_marketplace.applications.arxiv.integrations``. The library
blocks, so calls run in a worker thread. Dates are ISO strings (tools return
JSON).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from naas_abi_sdk.integration import (
    Integration,
    IntegrationConfiguration,
    IntegrationConnectionError,
)


def _arxiv() -> Any:
    import arxiv  # type: ignore[import-untyped]

    return arxiv


@dataclass
class ArXivIntegrationConfiguration(IntegrationConfiguration):
    max_results: int = 10
    # The arxiv library (tests pass a fake).
    library: Callable[[], Any] = field(default=_arxiv, repr=False)


def paper_record(paper: Any) -> dict[str, Any]:
    return {
        "id": paper.entry_id.split("/")[-1],
        "title": paper.title,
        "authors": [str(author) for author in paper.authors],
        "summary": paper.summary,
        "published": paper.published.isoformat() if paper.published else None,
        "updated": paper.updated.isoformat() if paper.updated else None,
        "categories": list(paper.categories),
        "links": [link.href for link in paper.links],
        "pdf_url": paper.pdf_url,
    }


class ArXivIntegration(Integration):
    """Search papers and read one paper's metadata."""

    def __init__(self, configuration: ArXivIntegrationConfiguration):
        super().__init__(configuration)
        self.configuration = configuration

    async def _results(self, **search: Any) -> list[dict[str, Any]]:
        def fetch() -> list[dict[str, Any]]:
            arxiv = self.configuration.library()
            return [
                paper_record(p) for p in arxiv.Client().results(arxiv.Search(**search))
            ]

        try:
            return await asyncio.to_thread(fetch)
        except Exception as exc:  # the library raises its own types
            raise IntegrationConnectionError(f"ArXiv request failed: {exc!s}") from exc

    async def search_papers(
        self, query: str, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        """Papers matching ``query``."""
        return await self._results(
            query=query, max_results=max_results or self.configuration.max_results
        )

    async def get_paper(self, paper_id: str) -> dict[str, Any]:
        """Metadata of one paper."""
        papers = await self._results(id_list=[paper_id])
        if not papers:
            raise IntegrationConnectionError(f"ArXiv paper {paper_id} not found")
        return papers[0]
