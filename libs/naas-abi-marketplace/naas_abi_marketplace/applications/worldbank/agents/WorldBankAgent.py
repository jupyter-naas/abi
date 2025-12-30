from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)
from naas_abi_marketplace.applications.worldbank import ABIModule

NAME = "WorldBank"
DESCRIPTION = "Helps you interact with World Bank data for economic and development indicators."
SYSTEM_PROMPT = """<role>
You are a World Bank Agent with expertise in economic data, development indicators, and global statistics.
</role>

<objective>
Help users understand World Bank capabilities and access economic data, indicators, and development statistics.
</objective>

<context>
You currently do not have access to World Bank tools. You can only provide general information and guidance about World Bank services and data access.
</context>

<tasks>
- Provide information about World Bank data features
- Explain economic indicators and development data
- Guide users on data analysis and interpretation
</tasks>

<operating_guidelines>
- Provide clear, accurate information about economic data
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or retrieve data without tools
- Only provide general information and guidance
- Do not make assumptions about economic indicators or statistics
</constraints>
"""
SUGGESTIONS: list = []


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> IntentAgent:
    # Init
    module = ABIModule.get_instance()

    # Define model
    from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1 import model

    # Define tools (none initially)
    tools: list = []

    # Define intents
    intents: list = [
        Intent(
            intent_value="Get information about World Bank data features",
            intent_type=IntentType.RAW,
            intent_target="World Bank provides economic data, development indicators, and global statistics. I can provide general information, but I currently do not have access to World Bank tools to retrieve data."
        ),
        Intent(
            intent_value="Understand economic indicators and development data",
            intent_type=IntentType.RAW,
            intent_target="Economic indicators include GDP, inflation, and development metrics. I can explain the concepts, but I currently do not have access to tools to retrieve economic data."
        ),
    ]

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return WorldBankAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class WorldBankAgent(IntentAgent):
    pass

