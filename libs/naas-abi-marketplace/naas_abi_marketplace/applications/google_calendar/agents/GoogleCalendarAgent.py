from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)
from naas_abi_marketplace.applications.google_calendar import ABIModule

NAME = "Google_Calendar"
DESCRIPTION = "Helps you interact with Google Calendar for scheduling and event management."
SYSTEM_PROMPT = """<role>
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
SUGGESTIONS: list = []


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> IntentAgent:
    # Init
    module = ABIModule.get_instance()

    # Define model
    from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1 import model

    # Define tools (none initially)
    tools: list = []

    # Define intents
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

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return GoogleCalendarAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class GoogleCalendarAgent(IntentAgent):
    pass

