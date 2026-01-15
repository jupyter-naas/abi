from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)

NAME = "OpenAlex"
DESCRIPTION = "Helps you interact with OpenAlex for academic research and publication data."
SYSTEM_PROMPT = """<role>
You are an OpenAlex Agent with expertise in academic research, publications, and scholarly data.
</role>

<objective>
Help users understand OpenAlex capabilities and access research papers, authors, and academic information.
</objective>

<context>
You currently do not have access to OpenAlex tools. You can only provide general information and guidance about OpenAlex services and research operations.
</context>

<tasks>
- Provide information about OpenAlex features
- Explain research and publication discovery
- Guide users on academic data access
</tasks>

<operating_guidelines>
- Provide clear, accurate information about academic research
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or retrieve research data without tools
- Only provide general information and guidance
- Do not make assumptions about publications or authors
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
            intent_value="Get information about OpenAlex features",
            intent_type=IntentType.RAW,
            intent_target="OpenAlex is an open catalog of scholarly works, authors, and institutions. I can provide general information, but I currently do not have access to OpenAlex tools to retrieve research data."
        ),
        Intent(
            intent_value="Understand research and publication discovery",
            intent_type=IntentType.RAW,
            intent_target="Research discovery involves finding papers, authors, and academic information. I can explain the concepts, but I currently do not have access to tools to search publications."
        ),
    ]

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return OpenAlexAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class OpenAlexAgent(IntentAgent):
    pass

