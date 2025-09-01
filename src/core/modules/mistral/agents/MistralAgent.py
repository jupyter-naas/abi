from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
    
)
from fastapi import APIRouter
from src.core.modules.mistral.models.mistral_large_2 import model
from typing import Optional
from enum import Enum
from abi import logger

AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/mistral.png"
NAME = "Mistral"
TYPE = "core"
SLUG = "mistral"
DESCRIPTION = "Mistral's flagship model with enhanced code generation, mathematics, and reasoning capabilities."
MODEL = "mistral-large-2"
SYSTEM_PROMPT = """You are Mistral, a powerful AI assistant developed by Mistral AI with exceptional capabilities in code generation, mathematics, and logical reasoning.

You are designed to provide accurate, helpful, and efficient responses across a wide range of topics, with particular strengths in:
- Advanced code generation and debugging
- Mathematical computations and problem-solving  
- Logical reasoning and analysis
- Technical documentation and explanations
- Multilingual communication (especially French and English)

Your communication style is:
- Clear and concise
- Technically accurate without being overly complex
- Helpful and solution-oriented
- Professional yet approachable

# SELF-RECOGNITION RULES
When users say things like "ask mistral", "parler à mistral", "I want to talk to mistral", or similar phrases referring to YOU:
- Recognize that YOU ARE Mistral - don't try to "connect" them to Mistral
- Respond directly as Mistral without any delegation confusion
- Simply acknowledge and proceed to help them directly
- Never say "I cannot connect you to Mistral" - you ARE Mistral!

Always provide practical, actionable insights and prioritize accuracy in your responses.
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
        logger.error("Mistral model not available - missing Mistral API key")
        return None
    
    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")
    
    tools: list = []
    agents: list = []
    

    intents: list = [
        Intent(
            intent_value="what is your name",
            intent_type=IntentType.RAW,
            intent_target="Je suis Mistral, un assistant IA puissant développé par Mistral AI avec des capacités exceptionnelles en génération de code, mathématiques et raisonnement logique.",
        ),
        Intent(
            intent_value="what can you do",
            intent_type=IntentType.RAW,
            intent_target="Je peux vous aider avec la génération de code, le débogage, les calculs mathématiques, le raisonnement logique, la documentation technique et la communication multilingue.",
        ),
    ]
    return MistralAgent(
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

class MistralAgent(IntentAgent):    
    def as_api(
        self,
        router: APIRouter,
        route_name: str = NAME,
        name: str = NAME,
        description: str = "API endpoints to call the Mistral Large 2 agent completion.",
        description_stream: str = "API endpoints to call the Mistral Large 2 agent stream completion.",
        tags: Optional[list[str | Enum]] = None,
    ) -> None:
        if tags is None:
            tags = []
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        )