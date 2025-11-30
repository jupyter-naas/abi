"""
🚧 NOT FUNCTIONAL YET - Model Configuration Template
gpt-4o model configuration for Treasurer domain expert
"""

from langchain_openai import ChatOpenAI
from naas_abi import secret
from naas_abi_core import logger


def create_model():
    """Create gpt-4o model for Treasurer - NOT FUNCTIONAL YET"""
    logger.warning("🚧 gpt-4o model not functional yet - template only")

    api_key = secret.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not found in environment")
        return None

    # Model configuration optimized for treasurer domain
    model = ChatOpenAI(
        model="gpt-4o",
        api_key=api_key,
        temperature=0,
        max_tokens=4000,
        # Domain-specific optimizations would go here
    )

    return model


# Model instance - NOT FUNCTIONAL YET
model = None  # Would be: create_model()
