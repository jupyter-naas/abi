from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)


class AirtableAgent(IntentAgent):
    name: str = "Airtable"
    description: str = "Helps you interact with Airtable for database and spreadsheet management."
    system_prompt: str = """<role>
You are an Airtable Agent with expertise in database management and collaborative data organization.
</role>

<objective>
Help users understand Airtable capabilities and manage databases, records, and collaborative workspaces.
</objective>

<context>
You currently do not have access to Airtable tools. You can only provide general information and guidance about Airtable services and database operations.
</context>

<tasks>
- Provide information about Airtable database features
- Explain record management and collaboration
- Guide users on Airtable capabilities and best practices
</tasks>

<operating_guidelines>
- Provide clear, accurate information about database management
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or access data without tools
- Only provide general information and guidance
- Do not make assumptions about database structure or records
</constraints>
"""
    suggestions: list = []

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "AirtableAgent":
        from naas_abi_core.engine.context import get_default_model_registry

        registry = get_default_model_registry()
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()
        embedding_model = registry.get_default_embedding_model().model

        tools: list = []
        intents: list = [
            Intent(
                intent_value="Get information about Airtable databases",
                intent_type=IntentType.RAW,
                intent_target="Airtable is a cloud-based database platform that combines spreadsheet functionality with database features. I can provide general information, but I currently do not have access to Airtable tools to access databases."
            ),
            Intent(
                intent_value="Understand record management and collaboration",
                intent_type=IntentType.RAW,
                intent_target="Record management involves creating, updating, and organizing data records. I can explain the concepts, but I currently do not have access to tools to manage records."
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
