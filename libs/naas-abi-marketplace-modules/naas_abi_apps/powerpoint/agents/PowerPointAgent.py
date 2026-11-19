"""PowerPoint agent: an SDK Agent hosted by the remote ``powerpoint`` module.

The in-engine agent was a custom LangGraph (template injection, draft
validation, markdown to JSON, JSON to pptx) that could not be built: it read a
``naas_api_key`` the module did not configure and a template missing from the
repository. This one keeps its brief-to-deck method in the prompt and does the
work with tools: read the template, create the deck, find presentations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from naas_abi_apps.common.agents import build_agent, tools_prompt
from naas_abi_apps.common.sparql_templates import module_queries, query_tools
from naas_abi_apps.powerpoint.integrations.PowerPointIntegration import (
    PowerPointIntegrationConfiguration,
    as_tools,
)
from naas_abi_apps.powerpoint.pipelines.AddPowerPointPresentationPipeline import (
    AddPowerPointPresentationPipelineParameters,
)
from naas_abi_apps.powerpoint.workflows.CreatePresentationFromTemplateWorkflow import (
    CreatePresentationFromTemplateWorkflowParameters,
)
from naas_abi_sdk.agents import Agent

NAME = "PowerPoint"
DESCRIPTION = "An agent specialized in creating PowerPoint presentations."
SYSTEM_PROMPT = """<role>
You are PowerPoint, an agent that converts a user brief into a structured PowerPoint presentation built from a template.
You never invent facts; you structure, adapt, and clearly label content from the brief.
</role>

<objective>
Create a clear, audience-aligned presentation that uses the template's slides as building blocks and honors the brief's objectives and constraints.
</objective>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
- First read the template with powerpoint_get_all_shapes_and_slides: each template slide has a slide_number, and each text shape a shape_id and a shape_alt_text saying what goes in it.
- From the brief, identify the number of slides (mandatory), the target audience and the objective. Only ask about what is missing.
- Propose the slide structure (Slide 1 - Title: Description, ...) and validate it with the user.
- Draft each slide in markdown: the template slide it uses, the text of each shape, and the sources. Iterate until the user validates.
- Then call create_presentation_from_template with, for each slide, its template_slide_number, the shapes (shape_id and text) and the sources.
- Give the user the download URL when there is one, otherwise the storage path, and the presentation URI.
- Use powerpoint_search_presentation_by_name to find presentations already created.
</operating_guidelines>

<constraints>
- You must know the number of slides to produce
- Do not alter numbers; if you must round, state the rule (e.g., 1 decimal)
- Always cite data sources with source URLs
- You can only update the text of shapes, not images, videos or tables
</constraints>
"""


def build_tools(
    template: bytes, workflow: Any, pipeline: Any, triple_store: Any
) -> list[Any]:
    from langchain_core.tools import StructuredTool

    async def create(**arguments: Any) -> Any:
        return await workflow.run(
            CreatePresentationFromTemplateWorkflowParameters(**arguments)
        )

    async def add(**arguments: Any) -> Any:
        graph = await pipeline.run(
            AddPowerPointPresentationPipelineParameters(**arguments)
        )
        return {"triples": len(graph)}

    return [
        *as_tools(PowerPointIntegrationConfiguration(template=template)),
        StructuredTool(
            name="create_presentation_from_template",
            description="Creates a PowerPoint presentation from the template and slide contents (template slide, shape texts, sources)",
            coroutine=create,
            args_schema=CreatePresentationFromTemplateWorkflowParameters,
        ),
        StructuredTool(
            name="add_powerpoint_presentation",
            description="Adds a PowerPoint presentation stored in object storage to the knowledge graph.",
            coroutine=add,
            args_schema=AddPowerPointPresentationPipelineParameters,
        ),
        *query_tools(module_queries(Path(__file__).resolve().parents[1]), triple_store),
    ]


async def create_agent(
    engine: Any, module_id: str, *, tools: list[Any], chat_model: str = ""
) -> Agent:
    return await build_agent(
        engine,
        module_id,
        name=NAME,
        description=DESCRIPTION,
        system_prompt=tools_prompt(SYSTEM_PROMPT, tools),
        tools=tools,
        chat_model=chat_model,
    )
