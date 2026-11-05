"""GitHub agent: an SDK IntentAgent hosted by the remote ``github`` module."""

from __future__ import annotations

from typing import Any

from naas_abi_apps.common.agents import build_agent, tools_prompt
from naas_abi_apps.github.agents.GitHubAgentIntents import INTENTS
from naas_abi_apps.github.integrations.GitHubGraphqlIntegration import (
    GitHubGraphqlIntegrationConfiguration,
)
from naas_abi_apps.github.integrations.GitHubGraphqlIntegration import (
    as_tools as graphql_tools,
)
from naas_abi_apps.github.integrations.GitHubIntegration import (
    GitHubIntegrationConfiguration,
)
from naas_abi_apps.github.integrations.GitHubIntegration import (
    as_tools as rest_tools,
)
from naas_abi_sdk.agents import Agent

NAME = "GitHub"
DESCRIPTION = "Helps you interact with GitHub through its REST API and GraphQL API."
SYSTEM_PROMPT = """<role>
You are a GitHub Agent with expertise in repository management, issue tracking, project management, and collaboration workflows.
</role>

<objective>
Help users effectively manage their GitHub repositories, issues, pull requests, projects, and collaboration workflows.
</objective>

<context>
You have access to GitHub tools for GitHub operations.
</context>

<tasks>
- Analyze user requests and identify required GitHub operations
- Validate input parameters before executing any tool
- Execute GitHub operations using appropriate tools
- Provide clear, informative responses about completed actions
</tasks>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
- Validate that all required parameters are provided and valid before using tool.
- Use descriptive titles and detailed descriptions when creating issues or pull requests
- Provide clear, concise responses with relevant information from tool responses
</operating_guidelines>

<constraints>
- Only use the provided GitHub tools - do not make assumptions about external APIs
- Do not attempt operations beyond the scope of the available tools
</constraints>
"""


def tools_for(access_token: str | None) -> list[Any]:
    """The REST and GraphQL tools, or none without a token."""
    if not access_token:
        return []
    return rest_tools(
        GitHubIntegrationConfiguration(access_token=access_token)
    ) + graphql_tools(GitHubGraphqlIntegrationConfiguration(access_token=access_token))


async def create_agent(
    engine: Any, module_id: str, *, access_token: str | None, chat_model: str = ""
) -> Agent:
    tools = tools_for(access_token)
    names = {tool.name for tool in tools}
    return await build_agent(
        engine,
        module_id,
        name=NAME,
        description=DESCRIPTION,
        system_prompt=tools_prompt(SYSTEM_PROMPT, tools),
        tools=tools,
        intents=[i for i in INTENTS if i.intent_target in names],
        chat_model=chat_model,
    )
