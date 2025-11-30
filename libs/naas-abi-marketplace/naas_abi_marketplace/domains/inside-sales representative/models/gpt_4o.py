"""
🚧 NOT FUNCTIONAL YET - Model Configuration Template
gpt-4o model configuration for Inside Sales Representative domain expert
"""

from langchain_openai import ChatOpenAI
from naas_abi import secret
from naas_abi_core import logger


def create_model():
    """Create gpt-4o model for Inside Sales Representative - NOT FUNCTIONAL YET"""
    logger.warning("🚧 gpt-4o model not functional yet - template only")

    api_key = secret.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not found in environment")
        return None

    # Model configuration optimized for inside sales representative domain
    model = ChatOpenAI(
        model="gpt-4o",
        api_key=api_key,
        temperature=0.2,
        max_tokens=4000,
        # Domain-specific optimizations would go here
    )

    return model


# Model instance - NOT FUNCTIONAL YET
model = None  # Would be: create_model()
