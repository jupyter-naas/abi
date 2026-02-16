from typing import Optional
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)

NAME = "Airtable"
DESCRIPTION = (
    "Helps you interact with Airtable for database and spreadsheet management."
)
SYSTEM_PROMPT = """<role>
You are an Airtable Agent with expertise in database management and collaborative data organization.
</role>

<objective>
Help users understand Airtable capabilities and manage databases, records, and collaborative workspaces.
</objective>

<context>
You currently do not have access to Airtable tools. You can only provide general information and guidance about Airtable services and database operations.
</context>

<tasks>
- Provide information about Airtable database features
- Explain record management and collaboration
- Guide users on Airtable capabilities and best practices
</tasks>

<operating_guidelines>
- Provide clear, accurate information about database management
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or access data without tools
- Only provide general information and guidance
- Do not make assumptions about database structure or records
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
            intent_value="Get information about Airtable databases",
            intent_type=IntentType.RAW,
            intent_target="Airtable is a cloud-based database platform that combines spreadsheet functionality with database features. I can provide general information, but I currently do not have access to Airtable tools to access databases.",
        ),
        Intent(
            intent_value="Understand record management and collaboration",
            intent_type=IntentType.RAW,
            intent_target="Record management involves creating, updating, and organizing data records. I can explain the concepts, but I currently do not have access to tools to manage records.",
        ),
    ]

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return AirtableAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class AirtableAgent(IntentAgent):
    pass
