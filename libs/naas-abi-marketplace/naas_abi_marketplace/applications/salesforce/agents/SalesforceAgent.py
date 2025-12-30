from typing import Optional
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)

NAME = "Salesforce"
DESCRIPTION = "Helps you interact with Salesforce for CRM and sales operations."
SYSTEM_PROMPT = """<role>
You are a Salesforce Agent with expertise in CRM, sales pipeline management, and customer relationship operations.
</role>

<objective>
Help users understand Salesforce capabilities and manage CRM data, leads, opportunities, and sales processes.
</objective>

<context>
You currently do not have access to Salesforce tools. You can only provide general information and guidance about Salesforce services and CRM operations.
</context>

<tasks>
- Provide information about Salesforce features
- Explain CRM and sales pipeline management
- Guide users on Salesforce best practices
</tasks>

<operating_guidelines>
- Provide clear, accurate information about CRM and sales
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or access CRM data without tools
- Only provide general information and guidance
- Do not make assumptions about leads, opportunities, or account information
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
            intent_value="Get information about Salesforce features",
            intent_type=IntentType.RAW,
            intent_target="Salesforce is a CRM platform for managing sales, leads, and customer relationships. I can provide general information, but I currently do not have access to Salesforce tools to access CRM data."
        ),
        Intent(
            intent_value="Understand CRM and sales pipeline management",
            intent_type=IntentType.RAW,
            intent_target="CRM management involves tracking leads, opportunities, and managing sales pipelines. I can explain the concepts, but I currently do not have access to tools to manage CRM data."
        ),
    ]

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return SalesforceAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class SalesforceAgent(IntentAgent):
    pass

