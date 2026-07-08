from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)


class ExchangeRatesAPIAgent(IntentAgent):
    name: str = "ExchangeRatesAPI"
    description: str = "Helps you interact with ExchangeRatesAPI for currency exchange rate information."
    system_prompt: str = """<role>
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
    suggestions: list = []

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "ExchangeRatesAPIAgent":
        from naas_abi_marketplace.applications.exchangeratesapi import ABIModule
        from naas_abi_marketplace.applications.exchangeratesapi.integrations.ExchangeratesapiIntegration import (
            ExchangeratesapiIntegrationConfiguration,
            as_tools,
        )



        abi_module = ABIModule.get_instance()

        registry = abi_module.engine.services.model_registry
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()
        embedding_model = registry.get_default_embedding_model().model

        module = ABIModule.get_instance()
        api_key = module.configuration.exchangeratesapi_api_key

        tools: list = []
        integration_config = ExchangeratesapiIntegrationConfiguration(api_key=api_key)
        tools += as_tools(integration_config)

        intents: list = [
            Intent(
                intent_value="Get exchange rate information",
                intent_type=IntentType.RAW,
                intent_target="I can provide general information about exchange rates and currency conversion. However, I currently do not have access to ExchangeRatesAPI tools to retrieve real-time data."
            ),
            Intent(
                intent_value="Understand currency conversion",
                intent_type=IntentType.RAW,
                intent_target="Currency conversion involves converting one currency to another using current exchange rates. I can explain the concepts, but I currently do not have access to tools to perform actual conversions."
            ),
        ]

        system_prompt = cls.system_prompt.replace(
            "[TOOLS]", "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])
        )
        if agent_configuration is None:
            agent_configuration = AgentConfiguration(system_prompt=system_prompt)
        if agent_shared_state is None:
            agent_shared_state = AgentSharedState(thread_id="0")

        return cls(
            name=cls.name,
            description=cls.description,
            chat_model=chat_model,
            embedding_model=embedding_model,
            tools=tools,
            agents=[],
            intents=intents,
            state=agent_shared_state,
            configuration=agent_configuration,
            memory=None,
        )
