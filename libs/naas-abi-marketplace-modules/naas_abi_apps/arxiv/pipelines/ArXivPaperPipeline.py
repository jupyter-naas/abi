"""Add an ArXiv paper to the knowledge graph (``pipeline.ar_xiv_paper_pipeline``).

Port of the in-engine pipeline, which wrote Turtle and PDF files to the local
disk and never reached the triple store: the paper now goes into the module's
named graph of the engine's triple store, and its PDF to object storage.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from naas_abi_apps.arxiv.integrations.ArXivIntegration import (
    ArXivIntegration,
    ArXivIntegrationConfiguration,
)
from naas_abi_apps.common.graph import ABI, BFO, ABIGraph
from naas_abi_sdk.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from pydantic import Field
from rdflib import Graph, Literal, URIRef


@dataclass
class ArXivPaperPipelineConfiguration(PipelineConfiguration):
    """triple_store / storage: the engine services (or fakes). download: fetches
    a PDF URL's bytes."""

    triple_store: Any = None
    storage: Any = None
    graph_name: str = "http://ontology.naas.ai/graph/arxiv"
    datastore_path: str = "arxiv"
    integration: ArXivIntegrationConfiguration = field(
        default_factory=ArXivIntegrationConfiguration
    )
    download: Any = None


class ArXivPaperPipelineParameters(PipelineParameters):
    paper_id: str = Field(..., description="ArXiv paper ID")
    download_pdf: bool = Field(True, description="Whether to download the paper's PDF")


async def _download(url: str) -> bytes:
    import httpx

    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content


def safe_name(title: str, paper_id: str) -> str:
    slug = re.sub(r"[\s-]+", "_", re.sub(r"[^\w\s-]", "", title)).lower()[:50]
    return f"{slug}_{paper_id.replace('/', '_')}"


class ArXivPaperPipeline(Pipeline[ArXivPaperPipelineParameters]):
    """Add an ArXiv paper (title, summary, authors, categories, publication date)
    to the knowledge graph, and optionally store its PDF."""

    def __init__(self, configuration: ArXivPaperPipelineConfiguration):
        super().__init__(configuration)
        self.configuration = configuration
        self.integration = ArXivIntegration(configuration.integration)

    @classmethod
    def New(cls, module: Any) -> ArXivPaperPipeline:
        services = module.engine.services
        return cls(
            ArXivPaperPipelineConfiguration(
                triple_store=services.triple_store,
                storage=services.object_storage,
                graph_name=module.configuration.graph_name,
                datastore_path=module.configuration.datastore_path,
            )
        )

    async def run(self, parameters: ArXivPaperPipelineParameters) -> Graph:
        data = await self.integration.get_paper(parameters.paper_id)
        graph = ABIGraph()
        paper = graph.add_individual_to_prefix(
            prefix=ABI,
            uid=data["id"],
            label=data["title"],
            is_a=ABI.ArXivPaper,
            description=data["summary"],
            url=data["pdf_url"],
            ontology_group="ArXivPaper",
        )
        if data["published"]:
            from datetime import datetime

            published = datetime.fromisoformat(data["published"])
            instant = graph.add_individual_to_prefix(
                prefix=ABI,
                uid=str(int(published.timestamp())),
                label=published.strftime("%Y-%m-%dT%H:%M:%S%z"),
                is_a=BFO.BFO_0000203,
            )
            graph.add((paper, BFO.BFO_0000222, instant))
        for name in data["authors"]:
            author = graph.add_individual_to_prefix(
                prefix=ABI,
                uid=name.replace(" ", "_"),
                label=name,
                is_a=ABI.ArXivAuthor,
                ontology_group="ArXivAuthor",
            )
            graph.add((paper, ABI.hasAuthor, author))
        for category in data["categories"]:
            node = graph.add_individual_to_prefix(
                prefix=ABI,
                uid=category,
                label=category,
                is_a=ABI.ArXivCategory,
                ontology_group="ArXivCategory",
            )
            graph.add((paper, ABI.hasCategory, node))

        if (
            parameters.download_pdf
            and data["pdf_url"]
            and self.configuration.storage is not None
        ):
            prefix = f"{self.configuration.datastore_path}/papers"
            key = f"{safe_name(data['title'], data['id'])}.pdf"
            content = await (self.configuration.download or _download)(data["pdf_url"])
            await self.configuration.storage.put_object(prefix, key, content)
            graph.add((paper, ABI.localFilePath, Literal(f"{prefix}/{key}")))

        if self.configuration.triple_store is not None:
            await self.configuration.triple_store.insert(
                graph, URIRef(self.configuration.graph_name)
            )
        return graph
