from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
    
)
from fastapi import APIRouter
from src.core.modules.claude.models.claude_3_5_sonnet import model
from typing import Optional
from enum import Enum
from abi import logger

AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/claude.png"
NAME = "Claude"
TYPE = "core"
SLUG = "claude"
DESCRIPTION = "Anthropic's most intelligent model with best-in-class reasoning capabilities and analysis."
MODEL = "claude-3-5-sonnet"
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

# SELF-RECOGNITION RULES
When users say things like "ask claude", "parler à claude", "I want to talk to claude", or similar phrases referring to YOU:
- Recognize that YOU ARE Claude - don't try to "connect" them to Claude
- Respond directly as Claude without any delegation confusion
- Simply acknowledge and proceed to help them directly
- Never say "I cannot ask Claude" or "I cannot connect you to Claude" - you ARE Claude!

You prioritize accuracy, helpfulness, and ethical considerations in all your responses.
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
        logger.error("Claude model not available - missing Anthropic API key")
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
            intent_target="I am Claude, a helpful AI assistant created by Anthropic. I excel at complex reasoning, analysis, and creative tasks.",
        ),
        Intent(
            intent_value="what can you do",
            intent_type=IntentType.RAW,
            intent_target="I can help with complex reasoning, critical thinking, analysis, creative writing, technical explanations, research, and providing balanced perspectives on various topics.",
        ),
    ]
    return ClaudeAgent(
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

class ClaudeAgent(IntentAgent):
    def as_api(
        self,
        router: APIRouter,
        route_name: str = NAME,
        name: str = NAME,
        description: str = "API endpoints to call the Claude agent completion.",
        description_stream: str = "API endpoints to call the Claude agent stream completion.",
        tags: Optional[list[str | Enum]] = None,
    ) -> None:
        if tags is None:
            tags = []
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        )