from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
    
)
from fastapi import APIRouter
from src.core.modules.llama.models.llama_3_3_70b import model
from typing import Optional
from enum import Enum
from abi import logger

AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/llama.jpeg"
NAME = "Llama"
TYPE = "core"
SLUG = "llama"
DESCRIPTION = "Meta's latest Llama model with 70B parameters, optimized for instruction-following and conversational dialogue."
MODEL = "llama-3-3-70b"
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

# SELF-RECOGNITION RULES
When users say things like "ask llama", "parler à llama", "I want to talk to llama", or similar phrases referring to YOU:
- Recognize that YOU ARE Llama - don't try to "connect" them to Llama
- Respond directly as Llama without any delegation confusion
- Simply acknowledge and proceed to help them directly
- Never say "I cannot connect you to Llama" - you ARE Llama!

You aim to be genuinely helpful while being honest about your capabilities and limitations.
"""
TEMPERATURE = 0
DATE = True
INSTRUCTIONS_TYPE = "system"
ONTOLOGY = True
SUGGESTIONS: list = []

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Optional[IntentAgent]:
    # Check if model is available
    if model is None:
        logger.error("Llama model not available - missing Meta API key")
        return None
    
    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")
    
    # Init
    tools: list = []
    agents: list = []

    intents: list = [
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
    ]
    return LlamaAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools,
        agents=agents,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    ) 

class LlamaAgent(IntentAgent):
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
            tags = []
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        )