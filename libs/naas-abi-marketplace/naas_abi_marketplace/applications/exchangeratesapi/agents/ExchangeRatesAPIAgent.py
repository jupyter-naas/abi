from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)
from naas_abi_marketplace.applications.exchangeratesapi import ABIModule

NAME = "ExchangeRatesAPI"
DESCRIPTION = (
    "Helps you interact with ExchangeRatesAPI for currency exchange rate information."
)
SYSTEM_PROMPT = """<role>
You are an ExchangeRatesAPI Agent with expertise in currency exchange rates and financial data.
</role>

<objective>
Help users access currency exchange rate information and understand exchange rate data.
</objective>

<context>
You currently do not have access to ExchangeRatesAPI tools. You can only provide general information and guidance about exchange rates and the ExchangeRatesAPI service.
</context>

<tasks>
- Provide information about currency exchange rates
- Explain ExchangeRatesAPI capabilities and features
- Guide users on how to use exchange rate data
</tasks>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
- Provide clear, accurate information about exchange rates
- Acknowledge when tools are not available
- Guide users on what information would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or retrieve real-time data without tools
- Only provide general information and guidance
- Do not make assumptions about specific exchange rates
</constraints>
"""
SUGGESTIONS: list = []


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> IntentAgent:
    # Init
    module = ABIModule.get_instance()
    api_key = module.configuration.exchangeratesapi_api_key

    # Define model
    from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1 import model

    # Define tools (none initially)
    tools: list = []
    from naas_abi_marketplace.applications.exchangeratesapi.integrations.ExchangeratesapiIntegration import (
        as_tools,
        ExchangeratesapiIntegrationConfiguration,
    )

    integration_config = ExchangeratesapiIntegrationConfiguration(api_key=api_key)
    tools += as_tools(integration_config)

    # Define intents
    intents: list = [
        Intent(
            intent_value="Get exchange rate information",
            intent_type=IntentType.RAW,
            intent_target="I can provide general information about exchange rates and currency conversion. However, I currently do not have access to ExchangeRatesAPI tools to retrieve real-time data.",
        ),
        Intent(
            intent_value="Understand currency conversion",
            intent_type=IntentType.RAW,
            intent_target="Currency conversion involves converting one currency to another using current exchange rates. I can explain the concepts, but I currently do not have access to tools to perform actual conversions.",
        ),
    ]

    # Set configuration
    system_prompt = SYSTEM_PROMPT.replace(
        "[TOOLS]", "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])
    )
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=system_prompt)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return ExchangeRatesAPIAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class ExchangeRatesAPIAgent(IntentAgent):
    pass
