from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)


class SharePointAgent(IntentAgent):
    name: str = "SharePoint"
    description: str = "Helps you interact with SharePoint for document management and collaboration."
    system_prompt: str = """<role>
You are a SharePoint Agent with expertise in document management, collaboration, and enterprise content management.
</role>

<objective>
Help users understand SharePoint capabilities and manage documents, sites, and collaborative workspaces.
</objective>

<context>
You currently do not have access to SharePoint tools. You can only provide general information and guidance about SharePoint services and document operations.
</context>

<tasks>
- Provide information about SharePoint features
- Explain document and site management
- Guide users on collaboration best practices
</tasks>

<operating_guidelines>
- Provide clear, accurate information about document management
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or access documents without tools
- Only provide general information and guidance
- Do not make assumptions about document content or structure
</constraints>
"""
    suggestions: list = []

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "SharePointAgent":

        from naas_abi_marketplace.applications.sharepoint import ABIModule


        abi_module = ABIModule.get_instance()

        registry = abi_module.engine.services.model_registry
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()
        embedding_model = registry.get_default_embedding_model().model

        tools: list = []
        intents: list = [
            Intent(
                intent_value="Get information about SharePoint features",
                intent_type=IntentType.RAW,
                intent_target="SharePoint is a document management and collaboration platform. I can provide general information, but I currently do not have access to SharePoint tools to access documents."
            ),
            Intent(
                intent_value="Understand document and site management",
                intent_type=IntentType.RAW,
                intent_target="Document management involves organizing, sharing, and collaborating on files. I can explain the concepts, but I currently do not have access to tools to manage documents."
            ),
        ]

        if agent_configuration is None:
            agent_configuration = AgentConfiguration(system_prompt=cls.system_prompt)
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
