from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)


class GoogleCalendarAgent(IntentAgent):
    name: str = "Google_Calendar"
    description: str = "Helps you interact with Google Calendar for scheduling and event management."
    system_prompt: str = """<role>
You are a Google Calendar Agent with expertise in scheduling, event management, and calendar operations.
</role>

<objective>
Help users understand Google Calendar capabilities and manage events, schedules, and calendars.
</objective>

<context>
You currently do not have access to Google Calendar tools. You can only provide general information and guidance about Google Calendar services and scheduling operations.
</context>

<tasks>
- Provide information about Google Calendar features
- Explain event management and scheduling
- Guide users on calendar best practices
</tasks>

<operating_guidelines>
- Provide clear, accurate information about calendar management
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or access calendar data without tools
- Only provide general information and guidance
- Do not make assumptions about event details or availability
</constraints>
"""
    suggestions: list = []

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "GoogleCalendarAgent":
        from naas_abi_core.engine.context import get_default_model_registry

        registry = get_default_model_registry()
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()
        embedding_model = registry.get_default_embedding_model().model

        tools: list = []
        intents: list = [
            Intent(
                intent_value="Get information about Google Calendar features",
                intent_type=IntentType.RAW,
                intent_target="Google Calendar is a time-management and scheduling service. I can provide general information, but I currently do not have access to Google Calendar tools to access events."
            ),
            Intent(
                intent_value="Understand event management and scheduling",
                intent_type=IntentType.RAW,
                intent_target="Event management involves creating, updating, and organizing calendar events. I can explain the concepts, but I currently do not have access to tools to manage events."
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
