from __future__ import annotations

from typing import Optional

from langchain_core.language_models import BaseChatModel

from naas_abi_core.models.Model import ChatModel
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)


class OpenRouterAgent(IntentAgent):
    name: str = "OpenRouter"
    description: str = "Helps you interact with OpenRouter for accessing multiple AI models."
    # Canonical model id this agent runs on (single source of truth): ``New``
    # builds its chat_model from it and the API/UI reads it via get_chat_model_id.
    MODEL_ID: str = "openrouter/free"
    logo_url: str = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSMyMkLa1_OdyK9b4LZTiDiR7W5SkPRtydKKw&s"
    suggestions: list = []
    system_prompt: str = """<role>
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

    @classmethod
    def get_chat_model_id(cls) -> Optional[str]:
        return cls.MODEL_ID

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "OpenRouterAgent":
        from naas_abi_marketplace.applications.openrouter import ABIModule
        from naas_abi_marketplace.applications.openrouter.integrations.OpenRouterAPIIntegration import (
            OpenRouterAPIIntegrationConfiguration,
            as_tools,
        )
        from naas_abi_marketplace.applications.openrouter.models.OpenRouterModel import (
            OpenRouterModel,
        )

        module = ABIModule.get_instance()
        api_key = module.configuration.openrouter_api_key
        object_storage = module.engine.services.object_storage

        # Prefer a registered canonical model; otherwise fall back to routing the
        # full OpenRouter model id (e.g. ``openrouter/free``) directly through the
        # OpenRouter API. Mirrors the logic in OpenRouterAgents.create_agents.
        registry = module.engine.services.model_registry
        lookup_id = (
            cls.MODEL_ID.rsplit("/", 1)[-1]
            if cls.MODEL_ID and "/" in cls.MODEL_ID
            else cls.MODEL_ID
        )
        chat_model: BaseChatModel | ChatModel
        if lookup_id in registry.list_canonical_ids():
            chat_model = registry.get_chat_model(lookup_id, provider="openrouter")
        else:
            chat_model = OpenRouterModel(api_key=api_key).get_model(cls.MODEL_ID)
        embedding_model = registry.get_default_embedding_model().model

        tools: list = []
        integration_config = OpenRouterAPIIntegrationConfiguration(
            api_key=api_key, object_storage=object_storage
        )
        tools += as_tools(integration_config)

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

        system_prompt = cls.system_prompt.replace(
            "[TOOLS]", "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])
        )
        if agent_configuration is None:
            agent_configuration = AgentConfiguration(system_prompt=system_prompt)
        if agent_shared_state is None:
            agent_shared_state = AgentSharedState()

        return cls(
            name=cls.name,
            description=cls.description,
            chat_model=chat_model,
            embedding_model=embedding_model,
            tools=tools,
            intents=intents,
            state=agent_shared_state,
            configuration=agent_configuration,
            memory=None,
        )
