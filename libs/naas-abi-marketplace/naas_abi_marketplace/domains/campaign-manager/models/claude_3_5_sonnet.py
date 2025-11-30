"""
🚧 NOT FUNCTIONAL YET - Model Configuration Template
claude-3-5-sonnet model configuration for Campaign Manager domain expert
"""

from langchain_anthropic import ChatAnthropic
from naas_abi import secret
from naas_abi_core import logger


def create_model():
    """Create claude-3-5-sonnet model for Campaign Manager - NOT FUNCTIONAL YET"""
    logger.warning("🚧 claude-3-5-sonnet model not functional yet - template only")

    api_key = secret.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY not found in environment")
        return None

    # Model configuration optimized for campaign manager domain
    model = ChatAnthropic(
        model="claude-3-5-sonnet",
        api_key=api_key,
        temperature=0.3,
        max_tokens=4000,
        # Domain-specific optimizations would go here
    )

    return model


# Model instance - NOT FUNCTIONAL YET
model = None  # Would be: create_model()
