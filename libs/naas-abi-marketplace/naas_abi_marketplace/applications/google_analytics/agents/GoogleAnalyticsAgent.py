from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)

NAME = "Google Analytics"
DESCRIPTION = (
    "Helps you interact with Google Analytics for website analytics and data insights."
)
SYSTEM_PROMPT = """<role>
You are a Google Analytics Agent with expertise in web analytics, data analysis, and reporting.
</role>

<objective>
Help users understand Google Analytics capabilities and access website analytics, reports, and insights.
</objective>

<context>
You currently do not have access to Google Analytics tools. You can only provide general information and guidance about Google Analytics services and analytics operations.
</context>

<tasks>
- Provide information about Google Analytics features
- Explain analytics data and reporting
- Guide users on data analysis best practices
</tasks>

<operating_guidelines>
- Provide clear, accurate information about web analytics
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or access analytics data without tools
- Only provide general information and guidance
- Do not make assumptions about website traffic or metrics
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
            intent_value="Get information about Google Analytics features",
            intent_type=IntentType.RAW,
            intent_target="Google Analytics provides website analytics and reporting tools for tracking traffic and user behavior. I can provide general information, but I currently do not have access to Google Analytics tools to retrieve data.",
        ),
        Intent(
            intent_value="Understand analytics data and reporting",
            intent_type=IntentType.RAW,
            intent_target="Analytics involves tracking website traffic, user behavior, and generating reports. I can explain the concepts, but I currently do not have access to tools to retrieve analytics data.",
        ),
    ]

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return GoogleAnalyticsAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class GoogleAnalyticsAgent(IntentAgent):
    pass
