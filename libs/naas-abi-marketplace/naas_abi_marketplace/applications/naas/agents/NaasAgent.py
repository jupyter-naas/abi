from typing import Optional

from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)
from naas_abi_core.module.Module import BaseModule
from naas_abi_marketplace.applications.naas import ABIModule

NAME = "Naas"
DESCRIPTION = "Manage all resources on Naas: workspaces, agents, ontologies, users, secrets, storage."
AVATAR_URL = "https://raw.githubusercontent.com/jupyter-naas/awesome-notebooks/refs/heads/master/.github/assets/logos/Naas.png"
SYSTEM_PROMPT = """<role>
You are Naas, an expert AI agent for managing, querying, and operating resources on the Naas platform. You have direct access to NaasIntegration tools to interact with Naas workspaces, users, ontologies, agents, secrets, and storage.
</role>

<objective>
Empower users to efficiently leverage Naas services by executing actions, retrieving information, and offering clear guidance related to Naas resources.
</objective>

<context>
You are available to authenticated users with access to NaasIntegration tools via an API key specified in their environment (.env) file. If you cannot access a tool, instruct the user to set or update their NAAS_API_KEY.
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
SUGGESTIONS: list[str] = []


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Agent:
    # Init module
    naas_api_key = ABIModule.get_instance().configuration.naas_api_key

    # Define model
    from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini import model

    # Define tools
    tools: list = []
    from naas_abi_marketplace.applications.naas.integrations.NaasIntegration import (
        NaasIntegrationConfiguration,
        as_tools,
    )
    naas_integration_config = NaasIntegrationConfiguration(api_key=naas_api_key)
    tools += as_tools(naas_integration_config)
    
    # Define configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    return NaasAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=[],
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class NaasAgent(Agent):
    pass
