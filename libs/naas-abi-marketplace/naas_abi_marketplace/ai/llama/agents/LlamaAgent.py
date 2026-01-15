from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)

NAME = "Llama"
DESCRIPTION = "Meta's latest Llama model with 70B parameters, optimized for instruction-following and conversational dialogue."
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/llama.jpeg"
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
SUGGESTIONS: list = []


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> IntentAgent:
    # Define model
    from naas_abi_marketplace.ai.llama.models.llama_3_3_70b import model

    # Define tools
    tools: list = []

    # Define agents
    agents: list = []

    # Define intents
    intents: list = [
        Intent(
            intent_value="general knowledge",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="conversation",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="writing assistance",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="creative tasks",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="brainstorming",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="help me write python code",
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

    return LlamaAgent(
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


class LlamaAgent(IntentAgent):
    pass
