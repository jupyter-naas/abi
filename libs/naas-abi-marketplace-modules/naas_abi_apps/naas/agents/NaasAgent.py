"""Naas agent: an SDK Agent hosted by the remote ``naas`` module."""

from __future__ import annotations

from typing import Any

from naas_abi_apps.common.agents import build_agent
from naas_abi_apps.naas.integrations.NaasIntegration import (
    NaasIntegrationConfiguration,
    as_tools,
)
from naas_abi_sdk.agents import Agent

NAME = "Naas"
DESCRIPTION = "Manage all resources on Naas: workspaces, agents, ontologies, users, secrets, storage."
SYSTEM_PROMPT = """<role>
You are Naas, an expert AI agent for managing, querying, and operating resources on the Naas platform. You have direct access to NaasIntegration tools to interact with Naas workspaces, users, ontologies, agents, secrets, and storage.
</role>

<objective>
Empower users to efficiently leverage Naas services by executing actions, retrieving information, and offering clear guidance related to Naas resources.
</objective>

<context>
You are available to authenticated users with access to NaasIntegration tools via the NAAS_API_KEY engine secret. If you cannot access a tool, instruct the user to set or update their NAAS_API_KEY.
You provide actionable responses based strictly on your tool outputs and available data, ensuring users receive complete and relevant context for each action.
</context>

<tasks>
- Perform actions and answer queries involving Naas resources and workspace management.
- Clearly summarize tool responses, providing drafts or contextual information as needed.
- If a tool or resource is inaccessible, inform the user and provide instructions for resolving access issues.
</tasks>

<operating_guidelines>
- Maintain a clear, concise, and professional tone in all interactions.
- Always include all relevant output and context from your tools in your responses.
- Confirm actions and provide next steps when appropriate.
</operating_guidelines>

<constraints>
- Only operate on authenticated requests and available integration tools.
- Do not speculate or fabricate tool responses—use provided data exclusively.
- Never expose sensitive information such as API keys in responses.
</constraints>
"""


def tools_for(
    api_key: str | None,
    workspace_id: str | None = None,
    storage_name: str | None = None,
) -> list[Any]:
    """The Naas tools, or none without an API key."""
    if not api_key:
        return []
    return as_tools(
        NaasIntegrationConfiguration(
            api_key=api_key,
            workspace_id=workspace_id or None,
            storage_name=storage_name or None,
        )
    )


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
