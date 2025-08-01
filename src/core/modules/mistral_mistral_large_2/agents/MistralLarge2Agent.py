from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
    MemorySaver,
)
from fastapi import APIRouter
from ..models.mistral_large_2 import model
from src import secret
from typing import Optional
from enum import Enum
import os
from datetime import datetime

NAME = "mistral-large-2"
AVATAR_URL = "https://docs.mistral.ai/img/logo_dark.svg"
DESCRIPTION = "Mistral's flagship model with enhanced code generation, mathematics, and reasoning capabilities."

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

Always provide practical, actionable insights and prioritize accuracy in your responses."""


class MistralLarge2Agent(IntentAgent):
    """Mistral's flagship model with enhanced code generation, mathematics, and reasoning capabilities."""
    
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
            tags = ["Mistral", "AI", "Code", "Mathematics", "Reasoning"]
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        )

    def hello(self) -> str:
        first_name = os.getenv("USER_FIRST_NAME", "there")
        current_time = datetime.now().strftime("%H:%M")
        
        return f"""
Bonjour {first_name}! Je suis Mistral, l'assistant IA développé par Mistral AI. Il est {current_time} et je suis prêt à vous aider.

Je suis spécialisé dans :
💻 Génération et débogage de code
🧮 Calculs mathématiques et résolution de problèmes
🧠 Raisonnement logique et analyse
📚 Documentation technique
🌍 Communication multilingue (français/anglais)

Comment puis-je vous assister aujourd'hui ?
"""


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Optional[IntentAgent]:
    # Check if Mistral API key is available
    if not secret.get("MISTRAL_API_KEY"):
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
        
    return MistralLarge2Agent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools,
        agents=agents,
        intents=[
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
        ],
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=MemorySaver(),
    ) 