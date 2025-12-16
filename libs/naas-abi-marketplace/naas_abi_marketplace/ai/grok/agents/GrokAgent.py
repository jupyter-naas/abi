from typing import Optional
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)

NAME = "Grok"
DESCRIPTION = "xAI's revolutionary AI with the highest intelligence scores globally, designed for truth-seeking and real-world understanding."
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/grok.jpg"
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

You aim to be genuinely helpful in understanding complex problems and reaching truthful conclusions, even when those conclusions challenge popular beliefs.
"""
SUGGESTIONS: list = []


def create_agent(
    agent_configuration: Optional[AgentConfiguration] = None,
    agent_shared_state: Optional[AgentSharedState] = None,
) -> IntentAgent:
    # Define model
    from naas_abi.core.grok.models.grok_4 import model

    # Define tools
    tools: list = []

    # Define agents
    agents: list = []

    # Define intents
    intents: list = [
        Intent(
            intent_value="search news about",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="search web about",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="search information about",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="analyze scientific problems",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="think critically",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="seek truth",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="challenge conventional views",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="reason rigorously",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
    ]

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    return GrokAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=agents,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class GrokAgent(IntentAgent):
    pass
