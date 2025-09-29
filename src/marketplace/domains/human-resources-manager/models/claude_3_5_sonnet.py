"""
🚧 NOT FUNCTIONAL YET - Model Configuration Template
claude-3-5-sonnet model configuration for Human Resources domain expert
"""

from langchain_anthropic import ChatAnthropic
from src import secret
from abi import logger

def create_model():
    """Create claude-3-5-sonnet model for Human Resources - NOT FUNCTIONAL YET"""
    logger.warning("🚧 claude-3-5-sonnet model not functional yet - template only")
    
    api_key = secret.get('ANTHROPIC_API_KEY')
    if not api_key:
        logger.error("ANTHROPIC_API_KEY not found in environment")
        return None
    
    # Model configuration optimized for human resources domain
    model = ChatAnthropic(
        model="claude-3-5-sonnet",
        api_key=api_key,
        temperature=0.1,  # Low temperature for professional accuracy
        max_tokens=4000,
        # Domain-specific optimizations would go here
    )
    
    return model

# Model instance - NOT FUNCTIONAL YET
model = None  # Would be: create_model()