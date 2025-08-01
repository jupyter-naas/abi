from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
    MemorySaver,
)
from fastapi import APIRouter
from ..models.llama_3_3_70b import model
from src import secret
from typing import Optional
from enum import Enum
import os
from datetime import datetime

NAME = "llama-3.3-70b-instruct"
AVATAR_URL = "https://github.com/meta-llama/llama/raw/main/Llama_Repo.jpeg"
DESCRIPTION = "Meta's latest Llama model with 70B parameters, optimized for instruction-following and conversational dialogue."

SYSTEM_PROMPT = """You are Llama, a helpful AI assistant created by Meta. You excel at following instructions, engaging in conversation, and assisting with a wide variety of tasks.

Your strengths include:
- Instruction-following and task completion
- Conversational dialogue and natural interaction
- General knowledge and reasoning
- Creative writing and content generation
- Code understanding and assistance
- Mathematical problem-solving

Your communication style is:
- Natural and conversational
- Helpful and responsive
- Clear and easy to understand
- Adaptable to different contexts
- Friendly and approachable

You aim to be genuinely helpful while being honest about your capabilities and limitations."""


class Llama33_70BAgent(IntentAgent):
    """Meta's latest Llama model with 70B parameters, optimized for instruction-following and conversational dialogue."""
    
    def as_api(
        self,
        router: APIRouter,
        route_name: str = NAME,
        name: str = NAME,
        description: str = "API endpoints to call the Llama 3.3 70B agent completion.",
        description_stream: str = "API endpoints to call the Llama 3.3 70B agent stream completion.",
        tags: Optional[list[str | Enum]] = None,
    ) -> None:
        if tags is None:
            tags = ["Meta", "Llama", "AI", "OpenSource", "Conversation"]
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        )

    def hello(self) -> str:
        first_name = os.getenv("USER_FIRST_NAME", "there")
        current_time = datetime.now().strftime("%H:%M")
        
        return f"""
Hello {first_name}! I'm Llama, Meta's AI assistant. It's {current_time} and I'm ready to help with whatever you need.

I'm great at:
💬 Natural conversation and dialogue
📝 Following instructions and completing tasks
🧠 General knowledge and reasoning
✨ Creative writing and content generation
💻 Code understanding and assistance
🔢 Mathematical problem-solving

What can I help you with today?
"""


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Optional[IntentAgent]:
    # Check if OpenAI API key is available (used for Llama via OpenAI-compatible endpoint)
    if not secret.get("OPENAI_API_KEY"):
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
        
    return Llama33_70BAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools,
        agents=agents,
        intents=[
            Intent(
                intent_value="what is your name",
                intent_type=IntentType.RAW,
                intent_target="I am Llama, a helpful AI assistant created by Meta. I'm designed for instruction-following and natural conversation.",
            ),
            Intent(
                intent_value="what can you do",
                intent_type=IntentType.RAW,
                intent_target="I can help with natural conversation, following instructions, creative writing, code assistance, mathematical problems, and general knowledge questions.",
            ),
        ],
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=MemorySaver(),
    ) 