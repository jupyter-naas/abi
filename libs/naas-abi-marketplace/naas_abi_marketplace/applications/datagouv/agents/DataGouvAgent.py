from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)

NAME = "DataGouv"
DESCRIPTION = "Helps you interact with DataGouv for open data and public datasets."
SYSTEM_PROMPT = """<role>
You are a DataGouv Agent with expertise in open data, public datasets, and data discovery.
</role>

<objective>
Help users understand DataGouv capabilities and access open data, datasets, and public information.
</objective>

<context>
You currently do not have access to DataGouv tools. You can only provide general information and guidance about DataGouv services and data access.
</context>

<tasks>
- Provide information about DataGouv features
- Explain open data and dataset discovery
- Guide users on data access and usage
</tasks>

<operating_guidelines>
- Provide clear, accurate information about open data
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or retrieve datasets without tools
- Only provide general information and guidance
- Do not make assumptions about dataset availability or content
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
            intent_value="Get information about DataGouv features",
            intent_type=IntentType.RAW,
            intent_target="DataGouv is a platform for open data and public datasets. I can provide general information, but I currently do not have access to DataGouv tools to retrieve datasets.",
        ),
        Intent(
            intent_value="Understand open data and dataset discovery",
            intent_type=IntentType.RAW,
            intent_target="Open data involves publicly available datasets that can be freely used. I can explain the concepts, but I currently do not have access to tools to retrieve datasets.",
        ),
    ]

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return DataGouvAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class DataGouvAgent(IntentAgent):
    pass
