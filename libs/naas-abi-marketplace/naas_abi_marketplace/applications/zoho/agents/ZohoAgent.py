from typing import Optional
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)

NAME = "Zoho"
DESCRIPTION = (
    "Helps you interact with Zoho for business applications and CRM operations."
)
SYSTEM_PROMPT = """<role>
You are a Zoho Agent with expertise in business applications, CRM, and productivity tools.
</role>

<objective>
Help users understand Zoho capabilities and manage business applications, CRM, and productivity workflows.
</objective>

<context>
You currently do not have access to Zoho tools. You can only provide general information and guidance about Zoho services and business operations.
</context>

<tasks>
- Provide information about Zoho features
- Explain CRM and business application management
- Guide users on Zoho best practices
</tasks>

<operating_guidelines>
- Provide clear, accurate information about business applications
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or access Zoho data without tools
- Only provide general information and guidance
- Do not make assumptions about business data or configurations
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
            intent_value="Get information about Zoho features",
            intent_type=IntentType.RAW,
            intent_target="Zoho provides business applications including CRM, email, and productivity tools. I can provide general information, but I currently do not have access to Zoho tools to manage applications.",
        ),
        Intent(
            intent_value="Understand CRM and business application management",
            intent_type=IntentType.RAW,
            intent_target="Business application management involves managing CRM data, contacts, and workflows. I can explain the concepts, but I currently do not have access to tools to manage applications.",
        ),
    ]

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return ZohoAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class ZohoAgent(IntentAgent):
    pass
