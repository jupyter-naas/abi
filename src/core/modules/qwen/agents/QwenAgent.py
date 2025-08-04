"""Qwen Agent for local AI interactions via Ollama.

This module provides the QwenAgent class for local AI conversations using
Alibaba's Qwen3 8B model through Ollama. Designed for privacy-focused,
offline AI interactions with strong multilingual and coding capabilities.
"""

from abi.services.agent.IntentAgent import IntentAgent, Intent, IntentType, AgentConfiguration
from ..models.qwen3_8b import model
from typing import Optional

NAME = "Qwen"
DESCRIPTION = "Local Qwen3 8B model via Ollama - privacy-focused AI for coding, reasoning, and multilingual tasks"

def create_agent() -> Optional[IntentAgent]:
    """Create and configure the Qwen agent.
    
    Returns:
        Optional[IntentAgent]: Configured Qwen agent, or None if model unavailable
        
    Raises:
        ValueError: If Qwen model is not available (Ollama not running or model not pulled)
    """
    # Check if model is available
    if not model:
        print("⚠️  Qwen model not available. Make sure Ollama is running and 'qwen3:8b' is pulled.")
        return None
    
    # Agent system prompt optimized for Qwen3's capabilities
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

Remember: You're running locally on this machine, ensuring complete privacy and offline functionality."""

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

    # Type safety check
    if not model:
        raise ValueError("Qwen model not available - Ollama not running or qwen3:8b not pulled")

    return IntentAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        intents=intents,
        configuration=AgentConfiguration(
            system_prompt=SYSTEM_PROMPT,
        ),
    )