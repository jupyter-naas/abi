"""ArXiv agent: an SDK Agent hosted by the remote ``arxiv`` module."""

from __future__ import annotations

from typing import Any

from naas_abi_apps.arxiv.integrations.ArXivIntegration import ArXivIntegration
from naas_abi_apps.arxiv.pipelines.ArXivPaperPipeline import (
    ArXivPaperPipeline,
    ArXivPaperPipelineParameters,
)
from naas_abi_apps.arxiv.queries import ArXivQueries
from naas_abi_apps.common.agents import build_agent
from naas_abi_sdk.agents import Agent

NAME = "ArXivAgent"
DESCRIPTION = "Search and analyze research papers from ArXiv"
SYSTEM_PROMPT = """You are an ArXiv research assistant. You can help users search for papers, get paper details, and analyze research trends.
You have access to the following tools:
- search_arxiv_papers: Search for papers on ArXiv
- get_arxiv_paper: Get metadata for a specific paper
- arxiv_paper_pipeline: Add papers to the knowledge graph and download PDFs
- query_arxiv_authors: Find the authors of a paper in the knowledge graph
- query_arxiv_papers: Find papers by author or category in the knowledge graph
- get_frequent_authors: Find which authors appear most often in the saved papers
- get_arxiv_schema: Get the ArXiv ontology
- execute_arxiv_query: Run a custom SPARQL query on the knowledge graph

When users ask about papers, first search for relevant papers using search_arxiv_papers.
Then you can get detailed information about specific papers using get_arxiv_paper.
Use arxiv_paper_pipeline to add important papers to the knowledge graph for future reference.
Use the query tools to search for information in papers you've already added to the knowledge graph."""


def build_tools(
    integration: ArXivIntegration, pipeline: ArXivPaperPipeline, queries: ArXivQueries
) -> list[Any]:
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    class SearchPapers(BaseModel):
        query: str = Field(..., description="Search query string")
        max_results: int | None = Field(
            None, description="Maximum number of results to return"
        )

    class GetPaper(BaseModel):
        paper_id: str = Field(..., description="ArXiv paper ID")

    class AuthorQuery(BaseModel):
        paper_id: str | None = Field(None, description="ArXiv paper ID")
        paper_title: str | None = Field(
            None, description="Title or part of the title of the paper"
        )

    class PaperQuery(BaseModel):
        author_name: str | None = Field(None, description="Name of the author")
        category: str | None = Field(None, description="ArXiv category")

    class SparqlQuery(BaseModel):
        query: str = Field(..., description="The SPARQL query to execute")

    class Empty(BaseModel):
        pass

    async def search(query: str, max_results: int | None = None) -> Any:
        return await integration.search_papers(query, max_results)

    async def get_paper(paper_id: str) -> Any:
        return await integration.get_paper(paper_id)

    async def add_paper(paper_id: str, download_pdf: bool = True) -> Any:
        graph = await pipeline.run(
            ArXivPaperPipelineParameters(paper_id=paper_id, download_pdf=download_pdf)
        )
        return {
            "paper_id": paper_id,
            "triples": len(graph),
            "graph_name": pipeline.configuration.graph_name,
        }

    async def authors(
        paper_id: str | None = None, paper_title: str | None = None
    ) -> Any:
        return await queries.query_authors(paper_id, paper_title)

    async def papers(
        author_name: str | None = None, category: str | None = None
    ) -> Any:
        return await queries.query_papers(author_name, category)

    async def frequent() -> Any:
        return await queries.frequent_authors()

    async def schema() -> Any:
        return queries.schema()

    async def execute(query: str) -> Any:
        return await queries.execute(query)

    def tool(name: str, description: str, coroutine: Any, schema_: type) -> Any:
        return StructuredTool(
            name=name, description=description, coroutine=coroutine, args_schema=schema_
        )

    return [
        tool("search_arxiv_papers", "Search for papers on ArXiv", search, SearchPapers),
        tool(
            "get_arxiv_paper",
            "Get metadata for a specific ArXiv paper",
            get_paper,
            GetPaper,
        ),
        tool(
            "arxiv_paper_pipeline",
            "Adds an ArXiv paper to the knowledge graph and optionally stores the PDF",
            add_paper,
            ArXivPaperPipelineParameters,
        ),
        tool(
            "query_arxiv_authors",
            "Find the authors of a paper by paper ID or title",
            authors,
            AuthorQuery,
        ),
        tool(
            "query_arxiv_papers",
            "Find papers by author name or category",
            papers,
            PaperQuery,
        ),
        tool(
            "get_frequent_authors",
            "Find which authors appear most frequently in your saved papers",
            frequent,
            Empty,
        ),
        tool(
            "get_arxiv_schema",
            "Get the ArXiv ontology schema in turtle format",
            schema,
            Empty,
        ),
        tool(
            "execute_arxiv_query",
            "Execute a custom SPARQL query against the knowledge graph",
            execute,
            SparqlQuery,
        ),
    ]


async def create_agent(
    engine: Any, module_id: str, *, tools: list[Any], chat_model: str = ""
) -> Agent:
    return await build_agent(
        engine,
        module_id,
        name=NAME,
        description=DESCRIPTION,
        system_prompt=SYSTEM_PROMPT,
        tools=tools,
        chat_model=chat_model,
    )
