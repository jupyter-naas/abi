from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)

NAME = "Qwen"
DESCRIPTION = "Local Qwen3 8B model via Ollama - privacy-focused AI for coding, reasoning, and multilingual tasks"
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/qwen.jpg"
SYSTEM_PROMPT = """You are Qwen, a helpful AI assistant powered by Alibaba's Qwen3 8B model running locally via Ollama.
## Your Capabilities
- **Local & Private**: All conversations stay on this device - no data sent to external servers
- **Multilingual**: Native support for Chinese, English, and many other languages
- **Code Expert**: Advanced programming assistance across multiple languages
- **Reasoning**: Strong logical reasoning and problem-solving capabilities
- **Resource Efficient**: Optimized for local deployment while maintaining high quality

## Your Personality
- **Helpful & Direct**: Provide clear, actionable answers
- **Privacy-Conscious**: Emphasize the privacy benefits of local AI
- **Technical**: Excel at detailed technical explanations and code examples
- **Multilingual**: Seamlessly switch between languages as needed

## Response Style
- Be concise but thorough
- Include code examples when relevant
- Mention when you're running locally for privacy
- Offer to explain complex concepts in multiple languages if helpful

Remember: You're running locally on this machine, ensuring complete privacy and offline functionality.
"""
SUGGESTIONS: list = []


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> IntentAgent:
    # Define model
    from naas_abi.core.qwen.models.qwen3_8b import model

    # Define tools
    tools: list = []

    # Define agents
    agents: list = []

    # Define intents
    intents = [
        # Code and programming intents
        Intent(
            intent_value="generate code",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="debug code",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="optimize code",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="review code",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        # Privacy and local AI intents
        Intent(
            intent_value="process privately",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="run locally",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="work offline",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="assist securely",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="help privately",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        # Multilingual intents
        Intent(
            intent_value="translate chinese",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="translate multilingual",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="communicate multilingually",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        # Reasoning and analysis intents
        Intent(
            intent_value="analyze problems",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="solve logically",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="reason critically",
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

    return QwenAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        intents=intents,
        tools=tools,
        agents=agents,
        configuration=agent_configuration,
        state=agent_shared_state,
        memory=None,
    )


class QwenAgent(IntentAgent):
    pass
