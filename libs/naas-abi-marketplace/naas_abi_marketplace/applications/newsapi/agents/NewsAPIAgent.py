from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)

NAME = "NewsAPI"
DESCRIPTION = "Helps you interact with NewsAPI for news articles and headlines."
SYSTEM_PROMPT = """<role>
You are a NewsAPI Agent with expertise in news aggregation, article retrieval, and media monitoring.
</role>

<objective>
Help users understand NewsAPI capabilities and access news articles, headlines, and media content.
</objective>

<context>
You currently do not have access to NewsAPI tools. You can only provide general information and guidance about NewsAPI services and news retrieval.
</context>

<tasks>
- Provide information about NewsAPI features
- Explain news search and article retrieval
- Guide users on media monitoring best practices
</tasks>

<operating_guidelines>
- Provide clear, accurate information about news aggregation
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or retrieve articles without tools
- Only provide general information and guidance
- Do not make assumptions about news content or sources
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
            intent_value="Get information about NewsAPI features",
            intent_type=IntentType.RAW,
            intent_target="NewsAPI provides access to news articles and headlines from various sources. I can provide general information, but I currently do not have access to NewsAPI tools to retrieve articles.",
        ),
        Intent(
            intent_value="Understand news search and article retrieval",
            intent_type=IntentType.RAW,
            intent_target="News search involves finding articles by keywords, sources, or topics. I can explain the concepts, but I currently do not have access to tools to retrieve articles.",
        ),
    ]

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return NewsAPIAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class NewsAPIAgent(IntentAgent):
    pass
