"""PubMed agent: an SDK Agent hosted by the remote ``pubmed`` module."""

from __future__ import annotations

import asyncio
from typing import Any

from naas_abi_apps.common.agents import build_agent
from naas_abi_apps.pubmed.pipelines.PubMedPipeline import (
    PubMedPipeline,
    PubMedPipelineParameters,
)
from naas_abi_sdk.agents import Agent

NAME = "PubMedAgent"
DESCRIPTION = "PubMedAgent is an agent that can search for papers in PubMed."
SYSTEM_PROMPT = """You are a PubMed Agent aimed to help users search for papers in PubMed.
When using tools, you might receive a Turtle serialized graph as a response.
You must always display the request results as a Markdown table.
"""
# Concurrent PubMed Central downloads, as in the in-engine thread pool.
DOWNLOADS = 10


def build_tools(pipeline: PubMedPipeline, storage: Any, prefix: str) -> list[Any]:
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    class DownloadPdf(BaseModel):
        pmcids: list[str] = Field(
            ..., description="PubMed Central identifiers (PMCID) of the papers"
        )

    async def search(**arguments: Any) -> str:
        graph = await pipeline.run(PubMedPipelineParameters(**arguments))
        return graph.serialize(format="turtle")

    async def download_pdf(pmcids: list[str]) -> str:
        slots = asyncio.Semaphore(DOWNLOADS)

        async def one(pmcid: str) -> None:
            async with slots:
                stream = await asyncio.to_thread(
                    pipeline.integration.download_pubmed_central_pdf, pmcid
                )
                content = await asyncio.to_thread(stream.read)
                await storage.put_object(prefix, f"{pmcid}.pdf", content)

        await asyncio.gather(*(one(pmcid) for pmcid in pmcids))
        return f"PDFs downloaded and saved under {prefix}."

    return [
        StructuredTool(
            name="search_downloadable_pubmed_papers",
            description="Search PubMed for papers within a given date range.",
            coroutine=search,
            args_schema=PubMedPipelineParameters,
        ),
        StructuredTool(
            name="download_pdf",
            description="Download a PDF from PubMed Central using it's PMCID",
            coroutine=download_pdf,
            args_schema=DownloadPdf,
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
