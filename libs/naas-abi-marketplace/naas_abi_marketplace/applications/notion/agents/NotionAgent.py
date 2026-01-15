from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)

NAME = "Notion"
DESCRIPTION = "Helps you interact with Notion for workspace and knowledge management."
SYSTEM_PROMPT = """<role>
You are a Notion Agent with expertise in workspace management, knowledge organization, and collaborative documentation.
</role>

<objective>
Help users understand Notion capabilities and manage workspaces, pages, and databases.
</objective>

<context>
You currently do not have access to Notion tools. You can only provide general information and guidance about Notion services and workspace operations.
</context>

<tasks>
- Provide information about Notion features
- Explain workspace and page management
- Guide users on knowledge organization best practices
</tasks>

<operating_guidelines>
- Provide clear, accurate information about workspace management
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or access workspace data without tools
- Only provide general information and guidance
- Do not make assumptions about page content or structure
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
            intent_value="Get information about Notion features",
            intent_type=IntentType.RAW,
            intent_target="Notion is a workspace and knowledge management platform. I can provide general information, but I currently do not have access to Notion tools to access workspaces."
        ),
        Intent(
            intent_value="Understand workspace and page management",
            intent_type=IntentType.RAW,
            intent_target="Workspace management involves organizing pages, databases, and content. I can explain the concepts, but I currently do not have access to tools to manage workspaces."
        ),
    ]

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return NotionAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class NotionAgent(IntentAgent):
    pass

