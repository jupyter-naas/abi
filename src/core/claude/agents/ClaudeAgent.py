from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
)
from typing import Optional

NAME = "Claude"
DESCRIPTION = "Anthropic's most intelligent model with best-in-class reasoning capabilities and analysis."
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/claude.png"
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
SUGGESTIONS: list = []

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> IntentAgent:  
    # Define model
    from src.core.claude.models.claude_4_5_sonnet import model
    
    # Init
    tools: list = []
    agents: list = []
    intents: list = [
        Intent(intent_value="help me with complex analysis", intent_type=IntentType.AGENT, intent_target="call_model"),
        Intent(intent_value="help me with research synthesis", intent_type=IntentType.AGENT, intent_target="call_model"),
        Intent(intent_value="help me with report writing", intent_type=IntentType.AGENT, intent_target="call_model"),
        Intent(intent_value="help me with data analysis", intent_type=IntentType.AGENT, intent_target="call_model"),
        Intent(intent_value="help me with academic writing", intent_type=IntentType.AGENT, intent_target="call_model"),
        Intent(intent_value="help me write python code", intent_type=IntentType.AGENT, intent_target="call_model"),
    ]

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

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
    pass