from langchain_openai import ChatOpenAI
from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
)
from fastapi import APIRouter
from typing import Optional
from pydantic import SecretStr
from enum import Enum
from src import secret

NAME = "PowerPoint"
DESCRIPTION = "A PowerPoint Assistant for creating and managing presentations."
MODEL = "gpt-4o"
TEMPERATURE = 0
AVATAR_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/Microsoft_Office_PowerPoint_%282019%E2%80%93present%29.svg/2203px-Microsoft_Office_PowerPoint_%282019%E2%80%93present%29.svg.png"
SYSTEM_PROMPT = """
## Role
You are a McKinsey & Company consultant very skilled in creating PowerPoint presentations.

## Objective
Your primary mission is to help users create quality briefs to create or update PowerPoint presentations using the tools provided.

## Context
You operate within a secure environment with access to PowerPoint integration tools for presentation creation and management.

## Tools
- PowerPoint integration tools for presentation operations

## Tasks
- Create new presentations
- Update existing presentations
- Generate slide content
- Format presentations
- For any other request not covered by the tools, just say you don't have access to the feature but the user can contact support@naas.ai to get access to the feature.

## Operating Guidelines
- When introducing yourself, state your goal and list your available tools with descriptions and template names for each tool
- Before creating or updating a presentation, ensure you gather required information needed from the user
- Provide clear and professional guidance on presentation structure and content

## Constraints
- Be concise and to the point
- Maintain professional tone
- Focus on quality presentation design principles
- Always gather requirements before starting work
"""

SUGGESTIONS: list[str] = []

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Optional[IntentAgent]:
    # Set model
    model = ChatOpenAI(
        model=MODEL,
        temperature=TEMPERATURE,
        api_key=SecretStr(secret.get('OPENAI_API_KEY'))
    )

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT
        )
    
    # Set shared state
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")
    
    # Initialize tools and integrations
    tools: list = []
    
    # TODO: Add PowerPoint integration tools when available
    # from src.marketplace.modules.applications.powerpoint.integrations.PowerPointIntegration import PowerPointIntegrationConfiguration
    # powerpoint_integration_config = PowerPointIntegrationConfiguration()
    # tools += PowerPointIntegration.as_tools(powerpoint_integration_config)

    intents: list = [
        Intent(intent_value="Create a new presentation", intent_type=IntentType.TOOL, intent_target="powerpoint_create"),
        Intent(intent_value="Update existing presentation", intent_type=IntentType.TOOL, intent_target="powerpoint_update"),
        Intent(intent_value="Generate slide content", intent_type=IntentType.TOOL, intent_target="powerpoint_generate"),
        Intent(intent_value="Format presentation", intent_type=IntentType.TOOL, intent_target="powerpoint_format"),
    ]

    return PowerPointAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools, 
        agents=[],
        intents=intents,
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=None
    ) 

class PowerPointAgent(IntentAgent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = "powerpoint", 
        name: str = NAME, 
        description: str = "API endpoints to call the PowerPoint assistant completion.", 
        description_stream: str = "API endpoints to call the PowerPoint assistant stream completion.",
        tags: Optional[list[str | Enum]] = None,
    ) -> None:
        if tags is None:
            tags = []
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        ) 