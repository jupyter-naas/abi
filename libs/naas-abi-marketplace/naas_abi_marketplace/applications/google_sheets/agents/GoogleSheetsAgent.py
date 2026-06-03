from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)


class GoogleSheetsAgent(IntentAgent):
    name: str = "Google_Sheets"
    description: str = "Helps you interact with Google Sheets for spreadsheet management and data analysis."
    system_prompt: str = """<role>
You are a Google Sheets Agent with expertise in spreadsheet management, data analysis, and collaborative editing.
</role>

<objective>
Help users understand Google Sheets capabilities and manage spreadsheets, data, and formulas.
</objective>

<context>
You currently do not have access to Google Sheets tools. You can only provide general information and guidance about Google Sheets services and spreadsheet operations.
</context>

<tasks>
- Provide information about Google Sheets features
- Explain spreadsheet management and formulas
- Guide users on data analysis best practices
</tasks>

<operating_guidelines>
- Provide clear, accurate information about spreadsheet management
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or access spreadsheet data without tools
- Only provide general information and guidance
- Do not make assumptions about spreadsheet content or structure
</constraints>
"""
    suggestions: list = []

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "GoogleSheetsAgent":
        from naas_abi_core.engine.context import get_default_model_registry

        registry = get_default_model_registry()
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()
        embedding_model = registry.get_default_embedding_model().model

        tools: list = []
        intents: list = [
            Intent(
                intent_value="Get information about Google Sheets features",
                intent_type=IntentType.RAW,
                intent_target="Google Sheets is a spreadsheet application with collaboration features. I can provide general information, but I currently do not have access to Google Sheets tools to access spreadsheets.",
            ),
            Intent(
                intent_value="Understand spreadsheet management and formulas",
                intent_type=IntentType.RAW,
                intent_target="Spreadsheet management involves organizing data, using formulas, and collaborating. I can explain the concepts, but I currently do not have access to tools to manage spreadsheets.",
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
