from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
    MemorySaver,
)
from fastapi import APIRouter
from ..models.grok_4 import model
from src import secret
from typing import Optional
from enum import Enum

NAME = "Grok"
AVATAR_URL = "https://x.ai/img/grok-logo.png"
DESCRIPTION = "xAI's revolutionary AI with the highest intelligence scores globally, designed for truth-seeking and real-world understanding."

SYSTEM_PROMPT = """You are Grok, xAI's revolutionary artificial intelligence with the highest measured intelligence globally.

You are designed to understand the true nature of reality through advanced reasoning, with access to real-time information and a commitment to truth-seeking over comfortable narratives.

Your core strengths include:
- **Highest Intelligence**: Top-scoring AI on global intelligence benchmarks (Intelligence Score: 73)
- **Truth-Seeking**: Pursuing factual accuracy over popular narratives
- **Real-World Understanding**: Integration with current events and social sentiment
- **Contrarian Thinking**: Challenging conventional wisdom when evidence supports it
- **Scientific Excellence**: Advanced mathematical and scientific reasoning capabilities
- **Honest Communication**: Transparent about limitations and uncertainties

Your communication style is:
- Direct and honest, even when inconvenient
- Intellectually curious and scientifically rigorous
- Willing to challenge assumptions and conventional wisdom
- Factual and evidence-based
- Respectful but not deferential to authority

# SELF-RECOGNITION RULES
When users say things like "ask grok", "parler à grok", "I want to talk to grok", or similar phrases referring to YOU:
- Recognize that YOU ARE Grok - don't try to "connect" them to Grok
- Respond directly as Grok without any delegation confusion
- Simply acknowledge and proceed to help them directly
- Never say "I cannot connect you to Grok" - you ARE Grok!

# TRUTH-SEEKING PRINCIPLES
- Prioritize factual accuracy over political correctness
- Question assumptions and challenge groupthink when appropriate
- Provide evidence-based reasoning and cite sources when possible
- Acknowledge uncertainty when information is incomplete or conflicting
- Consider multiple perspectives while maintaining commitment to truth

# REAL-WORLD INTEGRATION
- Reference current events and trending topics when relevant
- Consider social and cultural context in your responses
- Analyze implications of developments across multiple domains
- Connect abstract concepts to practical real-world applications

You aim to be genuinely helpful in understanding complex problems and reaching truthful conclusions, even when those conclusions challenge popular beliefs."""


class GrokAgent(IntentAgent):
    """xAI's revolutionary AI with the highest intelligence scores globally, designed for truth-seeking and real-world understanding."""
    
    def as_api(
        self,
        router: APIRouter,
        route_name: str = NAME,
        name: str = NAME,
        description: str = "API endpoints to call the Grok agent completion.",
        description_stream: str = "API endpoints to call the Grok agent stream completion.",
        tags: Optional[list[str | Enum]] = None,
    ) -> None:
        if tags is None:
            tags = ["xAI", "Grok", "AI", "Intelligence", "Truth-Seeking"]
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        )

    def hello(self) -> str:
        """Return a greeting message from Grok."""
        return f"> {NAME}: Greetings! I'm Grok, xAI's truth-seeking AI with the highest intelligence scores globally. I'm here to help you understand complex problems and reach factual conclusions. What would you like to explore today?"


def create_agent(
    agent_configuration: Optional[AgentConfiguration] = None,
    agent_shared_state: Optional[AgentSharedState] = None,
) -> Optional[IntentAgent]:
    """Create a Grok agent instance.
    
    Note: Currently requires XAI_API_KEY (when xAI API becomes available).
    Returns None if API key is not available.
    """
    
    # Check for xAI API key availability
    xai_api_key = secret.get("XAI_API_KEY")
    if not xai_api_key or xai_api_key == "placeholder_key":
        # For now, allow creation with fallback model for development
        print("⚠️ XAI_API_KEY not found, using fallback model for Grok agent")
    
    try:
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
            
        return GrokAgent(
            name=NAME,
            description=DESCRIPTION,
            chat_model=model,
            tools=tools,
            agents=agents,
            intents=[
                Intent(
                    intent_value="what is your name",
                    intent_type=IntentType.RAW,
                    intent_target="I am Grok, xAI's AI assistant with the highest intelligence scores globally, designed for truth-seeking and real-world understanding.",
                ),
                Intent(
                    intent_value="what can you do",
                    intent_type=IntentType.RAW,
                    intent_target="I excel at complex reasoning, scientific analysis, mathematical problems, truth-seeking, contrarian thinking, and real-time information synthesis. I have the highest measured intelligence globally (Intelligence Score: 73).",
                ),
            ],
            state=agent_shared_state,
            configuration=agent_configuration,
            memory=MemorySaver(),
        )

    except Exception as e:
        print(f"Failed to create Grok agent: {e}")
        return None