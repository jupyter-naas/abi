from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
)
from abi.services.agent.Agent import Agent
from src.core.modules.qwen.models.qwen3_8b import model
from typing import Optional
from abi import logger

AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/qwen.jpg"
NAME = "Qwen"
TYPE = "core"
SLUG = "qwen"
DESCRIPTION = "Local Qwen3 8B model via Ollama - privacy-focused AI for coding, reasoning, and multilingual tasks"
MODEL = "qwen3-8b"

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
        logger.error("Qwen model not available - missing Ollama API key")
        return None
    
    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    from langchain_core.tools import Tool
    from typing import List, Union
    
    tools: List[Union[Tool, Agent]] = []

    # Define Qwen-specific intents
    intents = [
        # Code and programming intents
        Intent(intent_type=IntentType.AGENT, intent_value="code with qwen", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="qwen code", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="local coding", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="private code help", intent_target=NAME),
        
        # Privacy and local AI intents
        Intent(intent_type=IntentType.AGENT, intent_value="private ai", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="local ai", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="offline ai", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="use qwen", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="switch to qwen", intent_target=NAME),
        
        # Multilingual intents
        Intent(intent_type=IntentType.AGENT, intent_value="qwen chinese", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="qwen 中文", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="multilingual help", intent_target=NAME),
        
        # Reasoning and analysis intents
        Intent(intent_type=IntentType.AGENT, intent_value="qwen reasoning", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="local reasoning", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="private analysis", intent_target=NAME),
    ]
    return QwenAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        intents=intents,
        tools=tools,
        configuration=agent_configuration,
        state=agent_shared_state,
        memory=None,
    )

class QwenAgent(IntentAgent):
    pass