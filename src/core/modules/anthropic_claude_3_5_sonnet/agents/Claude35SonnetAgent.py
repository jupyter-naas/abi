from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
    MemorySaver,
)
from fastapi import APIRouter
from ..models.claude_3_5_sonnet import model
from src import secret
from typing import Optional
from enum import Enum
import os
from datetime import datetime

NAME = "claude-3-5-sonnet"
AVATAR_URL = "https://assets.anthropic.com/m/0edc05fa8e30f2f9/original/Anthropic_Glyph_Black.svg"
DESCRIPTION = "Anthropic's most intelligent model with best-in-class reasoning capabilities and analysis."

SYSTEM_PROMPT = """You are Claude, a helpful, harmless, and honest AI assistant created by Anthropic.

You excel at complex reasoning, analysis, and creative tasks with a focus on:
- Advanced reasoning and critical thinking
- Complex analysis and problem-solving
- Ethical considerations and balanced perspectives
- Creative writing and content generation
- Technical explanations and documentation
- Research and information synthesis

Your communication style is:
- Thoughtful and nuanced
- Clear and well-structured
- Balanced and objective
- Helpful while being honest about limitations
- Respectful and considerate

You prioritize accuracy, helpfulness, and ethical considerations in all your responses."""


class Claude35SonnetAgent(IntentAgent):
    """Anthropic's most intelligent model with best-in-class reasoning capabilities and analysis."""
    
    def as_api(
        self,
        router: APIRouter,
        route_name: str = NAME,
        name: str = NAME,
        description: str = "API endpoints to call the Claude 3.5 Sonnet agent completion.",
        description_stream: str = "API endpoints to call the Claude 3.5 Sonnet agent stream completion.",
        tags: Optional[list[str | Enum]] = None,
    ) -> None:
        if tags is None:
            tags = ["Anthropic", "Claude", "AI", "Reasoning", "Analysis"]
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        )

    def hello(self) -> str:
        first_name = os.getenv("USER_FIRST_NAME", "there")
        current_time = datetime.now().strftime("%H:%M")
        
        return f"""
Hi {first_name}! I'm Claude, Anthropic's AI assistant. It's {current_time} and I'm here to help with thoughtful analysis and reasoning.

I excel at:
🧠 Complex reasoning and critical thinking
📊 Analysis and problem-solving
⚖️ Balanced perspectives and ethical considerations
✍️ Creative writing and content generation
📚 Technical explanations and documentation
🔍 Research and information synthesis

What would you like to explore together?
"""


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Optional[IntentAgent]:
    # Check if Anthropic API key is available
    if not secret.get("ANTHROPIC_API_KEY"):
        return None
    
    # Init
    tools: list = []
    agents: list = []
    
    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id=0)
        
    return Claude35SonnetAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools,
        agents=agents,
        intents=[
            Intent(
                intent_value="what is your name",
                intent_type=IntentType.RAW,
                intent_target="I am Claude, a helpful AI assistant created by Anthropic. I excel at complex reasoning, analysis, and creative tasks.",
            ),
            Intent(
                intent_value="what can you do",
                intent_type=IntentType.RAW,
                intent_target="I can help with complex reasoning, critical thinking, analysis, creative writing, technical explanations, research, and providing balanced perspectives on various topics.",
            ),
        ],
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=MemorySaver(),
    ) 