from typing import Optional
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)

NAME = "SharePoint"
DESCRIPTION = "Helps you interact with SharePoint for document management and collaboration."
SYSTEM_PROMPT = """<role>
You are a SharePoint Agent with expertise in document management, collaboration, and enterprise content management.
</role>

<objective>
Help users understand SharePoint capabilities and manage documents, sites, and collaborative workspaces.
</objective>

<context>
You currently do not have access to SharePoint tools. You can only provide general information and guidance about SharePoint services and document operations.
</context>

<tasks>
- Provide information about SharePoint features
- Explain document and site management
- Guide users on collaboration best practices
</tasks>

<operating_guidelines>
- Provide clear, accurate information about document management
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or access documents without tools
- Only provide general information and guidance
- Do not make assumptions about document content or structure
</constraints>
"""
SUGGESTIONS: list = []


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> IntentAgent:
    # Define model
    from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1 import model

    # Define tools (none initially)
    tools: list = []

    # Define intents
    intents: list = [
        Intent(
            intent_value="Get information about SharePoint features",
            intent_type=IntentType.RAW,
            intent_target="SharePoint is a document management and collaboration platform. I can provide general information, but I currently do not have access to SharePoint tools to access documents."
        ),
        Intent(
            intent_value="Understand document and site management",
            intent_type=IntentType.RAW,
            intent_target="Document management involves organizing, sharing, and collaborating on files. I can explain the concepts, but I currently do not have access to tools to manage documents."
        ),
    ]

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return SharePointAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class SharePointAgent(IntentAgent):
    pass

