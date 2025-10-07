from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
    
)
from typing import Optional

AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/mistral.png"
NAME = "Mistral"
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

# SELF-RECOGNITION RULES
When users say things like "ask mistral", "parler à mistral", "I want to talk to mistral", or similar phrases referring to YOU:
- Recognize that YOU ARE Mistral - don't try to "connect" them to Mistral
- Respond directly as Mistral without any delegation confusion
- Simply acknowledge and proceed to help them directly
- Never say "I cannot connect you to Mistral" - you ARE Mistral!

Always provide practical, actionable insights and prioritize accuracy in your responses.
"""
SUGGESTIONS: list = []

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> IntentAgent:    
    # Define model
    from src.core.mistral.models.mistral_large_2 import model
    
    # Define tools
    tools: list = []
    
    # Define agents
    agents: list = []
    
    # Define intents
    intents: list = [
        Intent(intent_value="generate code", intent_type=IntentType.AGENT, intent_target="call_model"),
        Intent(intent_value="review code", intent_type=IntentType.AGENT, intent_target="call_model"),
        Intent(intent_value="optimize code", intent_type=IntentType.AGENT, intent_target="call_model"),
        Intent(intent_value="document technical details", intent_type=IntentType.AGENT, intent_target="call_model"),
        Intent(intent_value="help with programming", intent_type=IntentType.AGENT, intent_target="call_model"),
    ]

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")
        
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
    pass