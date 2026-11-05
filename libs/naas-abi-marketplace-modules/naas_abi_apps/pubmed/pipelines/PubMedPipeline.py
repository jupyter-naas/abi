"""Search PubMed over a date range into an RDF graph (``pipeline.pub_med_pipeline``).

Port of the in-engine pipeline: same parameters and output. The PubMed client
blocks (requests, rate limit), so it runs in a worker thread.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal

from naas_abi_apps.pubmed.integrations.PubMedAPI import (
    PubMedAPIConfiguration,
    PubMedIntegration,
)
from naas_abi_sdk.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from pydantic import Field
from rdflib import Graph

logger = logging.getLogger(__name__)


class PubMedPipelineConfiguration(PipelineConfiguration):
    pass


class PubMedPipelineParameters(PipelineParameters):
    query: str = Field(..., description="The query to search for in PubMed")
    start_date: str = Field(..., description="The start date to search for in PubMed")
    end_date: str | None = Field(
        None, description="The end date to search for in PubMed"
    )
    sort: Literal["pub_date", "Author", "JournalName", "relevance"] | None = Field(
        "pub_date",
        description="Sort: 'pub_date', 'Author', 'JournalName', or 'relevance' (Best Match)",
    )
    downloadable_only: bool | None = Field(
        False, description="Only return papers downloadable from PubMedCentral"
    )
    max_results: int | None = Field(
        100, ge=1, le=10000, description="Maximum number of results to return"
    )


class PubMedPipeline(Pipeline[PubMedPipelineParameters]):
    """Search PubMed for papers within a given date range and return them as an RDF graph."""

    def __init__(
        self, configuration: PubMedPipelineConfiguration, integration: Any = None
    ):
        super().__init__(configuration)
        self.integration = integration or PubMedIntegration(PubMedAPIConfiguration())

    async def run(self, parameters: PubMedPipelineParameters) -> Graph:
        logger.info("PubMed search: %s", parameters.query)
        results = await asyncio.to_thread(
            self.integration.search_date_range,
            parameters.query,
            start_date=parameters.start_date,
            end_date=parameters.end_date,
            sort=parameters.sort,
            max_results=parameters.max_results,
        )
        graph = Graph()
        for result in results:
            if not parameters.downloadable_only or result.downloadUrl is not None:
                graph += result.rdf()
        return graph
