"""
Bitcoin Model Provider

Provides a unified interface for selecting and configuring language models for Bitcoin agents.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any, Union
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel

class ModelProvider(str, Enum):
    """Supported model providers for Bitcoin agents."""
    
    OPENAI = "openai"
    ANTHROPIC = "anthropic"

@dataclass
class ModelConfig:
    """Configuration for a language model.
    
    Attributes:
        provider (ModelProvider): The model provider (OpenAI, Anthropic, etc.)
        model_name (str): The name of the model to use
        temperature (float): The temperature setting for generation
        api_key (Optional[str]): API key for the provider
        max_tokens (Optional[int]): Maximum tokens to generate
        additional_kwargs (Dict[str, Any]): Additional provider-specific parameters
    """
    provider: ModelProvider
    model_name: str
    temperature: float = 0.7
    api_key: Optional[str] = None
    max_tokens: Optional[int] = None
    additional_kwargs: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.additional_kwargs is None:
            self.additional_kwargs = {}

def get_model(config: ModelConfig) -> BaseChatModel:
    """Get a language model based on the provided configuration.
    
    Args:
        config (ModelConfig): The model configuration
        
    Returns:
        BaseChatModel: The configured language model
        
    Raises:
        ValueError: If the provider is not supported
    """
    if config.provider == ModelProvider.OPENAI:
        model_kwargs = {}
        if config.max_tokens:
            model_kwargs["max_tokens"] = config.max_tokens
            
        return ChatOpenAI(
            model=config.model_name,
            temperature=config.temperature,
            api_key=config.api_key,
            **config.additional_kwargs,
            **model_kwargs
        )
    
    elif config.provider == ModelProvider.ANTHROPIC:
        model_kwargs = {}
        if config.max_tokens:
            model_kwargs["max_tokens"] = config.max_tokens
            
        return ChatAnthropic(
            model=config.model_name,
            temperature=config.temperature,
            api_key=config.api_key,
            **config.additional_kwargs,
            **model_kwargs
        )
    
    else:
        raise ValueError(f"Unsupported model provider: {config.provider}")

# Common model configurations for convenience
GPT35_CONFIG = ModelConfig(
    provider=ModelProvider.OPENAI,
    model_name="gpt-3.5-turbo",
    temperature=0.7
)

GPT4_CONFIG = ModelConfig(
    provider=ModelProvider.OPENAI,
    model_name="gpt-4",
    temperature=0.7
)

CLAUDE_INSTANT_CONFIG = ModelConfig(
    provider=ModelProvider.ANTHROPIC,
    model_name="claude-3-haiku-20240307",
    temperature=0.7
)

CLAUDE_OPUS_CONFIG = ModelConfig(
    provider=ModelProvider.ANTHROPIC,
    model_name="claude-3-opus-20240229",
    temperature=0.5
)

# Default model configuration
DEFAULT_CONFIG = GPT35_CONFIG 