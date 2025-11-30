from dataclasses import dataclass
from typing import List, Optional

import arxiv
from langchain_core.tools import StructuredTool
from naas_abi_core.integration import Integration
from naas_abi_core.integration.integration import IntegrationConfiguration
from pydantic import BaseModel, Field


@dataclass
class ArXivIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for ArXiv integration."""

    max_results: int = 10


class ArXivIntegration(Integration):
    """Integration with the ArXiv API."""

    __configuration: ArXivIntegrationConfiguration

    def __init__(self, configuration: ArXivIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__client = arxiv.Client()

    def search_papers(
        self, query: str, max_results: Optional[int] = None
    ) -> List[dict]:
        """Search for papers on ArXiv.

        Args:
            query: Search query string
            max_results: Maximum number of results to return

        Returns:
            List of paper metadata dictionaries
        """
        search = arxiv.Search(
            query=query, max_results=max_results or self.__configuration.max_results
        )

        results = []
        for paper in self.__client.results(search):
            results.append(
                {
                    "id": paper.entry_id.split("/")[-1],
                    "title": paper.title,
                    "authors": [str(author) for author in paper.authors],
                    "summary": paper.summary,
                    "published": paper.published,
                    "updated": paper.updated,
                    "categories": paper.categories,
                    "links": [link.href for link in paper.links],
                    "pdf_url": paper.pdf_url,
                }
            )
        return results

    def get_paper(self, paper_id: str) -> dict:
        """Get metadata for a specific paper.

        Args:
            paper_id: ArXiv paper ID

        Returns:
            Paper metadata dictionary
        """
        search = arxiv.Search(id_list=[paper_id])
        paper = next(self.__client.results(search))
        return {
            "id": paper.entry_id.split("/")[-1],
            "title": paper.title,
            "authors": [str(author) for author in paper.authors],
            "summary": paper.summary,
            "published": paper.published,
            "updated": paper.updated,
            "categories": paper.categories,
            "links": [link.href for link in paper.links],
            "pdf_url": paper.pdf_url,
        }

    @staticmethod
    def as_tools(configuration: ArXivIntegrationConfiguration) -> List[StructuredTool]:
        """Get tools for the ArXiv integration.

        Args:
            configuration: ArXiv integration configuration

        Returns:
            List of tools
        """
        integration = ArXivIntegration(configuration)

        class SearchPapersParameters(BaseModel):
            query: str = Field(..., description="Search query string")
            max_results: Optional[int] = Field(
                None, description="Maximum number of results to return"
            )

        class GetPaperParameters(BaseModel):
            paper_id: str = Field(..., description="ArXiv paper ID")

        return [
            StructuredTool(
                name="search_arxiv_papers",
                description="Search for papers on ArXiv",
                func=lambda **kwargs: integration.search_papers(**kwargs),
                args_schema=SearchPapersParameters,
            ),
            StructuredTool(
                name="get_arxiv_paper",
                description="Get metadata for a specific ArXiv paper",
                func=lambda **kwargs: integration.get_paper(**kwargs),
                args_schema=GetPaperParameters,
            ),
        ]
