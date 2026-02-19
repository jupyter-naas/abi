from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)
from naas_abi_marketplace.applications.openrouter import ABIModule

NAME = "OpenRouter"
DESCRIPTION = "Helps you interact with OpenRouter for accessing multiple AI models."
SYSTEM_PROMPT = """<role>
You are an OpenRouter Agent with expertise in AI model routing and multi-model access.
</role>

<objective>
Help users understand OpenRouter capabilities and access various AI models through a unified interface.
</objective>

<context>
You currently do not have access to OpenRouter tools. You can only provide general information and guidance about OpenRouter services and available AI models.
</context>

<tasks>
- Provide information about OpenRouter and available AI models
- Explain model routing and selection strategies
- Guide users on OpenRouter features and capabilities
</tasks>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
- Provide clear, accurate information about AI models and routing
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or route requests without tools
- Only provide general information and guidance
- Do not make assumptions about model availability or performance
</constraints>
"""
SUGGESTIONS: list = []


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> IntentAgent:
    # Init
    module = ABIModule.get_instance()
    api_key = module.configuration.openrouter_api_key
    object_storage = module.engine.services.object_storage

    # Define model
    from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1 import model

    # Define tools (none initially)
    tools: list = []
    from naas_abi_marketplace.applications.openrouter.integrations.OpenRouterAPIIntegration import (
        OpenRouterAPIIntegrationConfiguration,
        as_tools,
    )

    integration_config = OpenRouterAPIIntegrationConfiguration(
        api_key=api_key, object_storage=object_storage
    )
    tools += as_tools(integration_config)

    # Define intents
    intents: list = [
        Intent(
            intent_value="Get information about OpenRouter and available models",
            intent_type=IntentType.RAW,
            intent_target="OpenRouter provides access to multiple AI models through a unified API. I can provide general information, but I currently do not have access to OpenRouter tools to route requests.",
        ),
        Intent(
            intent_value="Understand AI model routing and selection",
            intent_type=IntentType.RAW,
            intent_target="Model routing involves selecting the best AI model for a given task. I can explain the concepts, but I currently do not have access to tools to perform routing.",
        ),
        Intent(
            intent_value="List all available models from OpenRouter",
            intent_type=IntentType.TOOL,
            intent_target="openrouter_list_models",
        ),
        Intent(
            intent_value="List all providers from OpenRouter",
            intent_type=IntentType.TOOL,
            intent_target="openrouter_list_providers",
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

    return OpenRouterAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class OpenRouterAgent(IntentAgent):
    pass
