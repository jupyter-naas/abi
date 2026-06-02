from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)


class GoogleDriveAgent(IntentAgent):
    name: str = "Google_Drive"
    description: str = "Helps you interact with Google Drive for file storage and management."
    system_prompt: str = """<role>
You are a Google Drive Agent with expertise in file storage, document management, and cloud storage operations.
</role>

<objective>
Help users understand Google Drive capabilities and manage files, folders, and storage.
</objective>

<context>
You currently do not have access to Google Drive tools. You can only provide general information and guidance about Google Drive services and file operations.
</context>

<tasks>
- Provide information about Google Drive features
- Explain file and folder management
- Guide users on storage best practices
</tasks>

<operating_guidelines>
- Provide clear, accurate information about file management
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or access files without tools
- Only provide general information and guidance
- Do not make assumptions about file content or structure
</constraints>
"""
    suggestions: list = []

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "GoogleDriveAgent":
        from naas_abi_core.engine.context import get_default_model_registry

        registry = get_default_model_registry()
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()
        embedding_model = registry.get_default_embedding_model().model

        tools: list = []
        intents: list = [
            Intent(
                intent_value="Get information about Google Drive features",
                intent_type=IntentType.RAW,
                intent_target="Google Drive is a file storage and synchronization service. I can provide general information, but I currently do not have access to Google Drive tools to access files.",
            ),
            Intent(
                intent_value="Understand file and folder management",
                intent_type=IntentType.RAW,
                intent_target="File management involves organizing, uploading, and sharing files. I can explain the concepts, but I currently do not have access to tools to manage files.",
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
