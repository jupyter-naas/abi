"""
🚧 NOT FUNCTIONAL YET - Model Configuration Template
deepseek-r1 model configuration for Data Engineer domain expert
"""

from langchain_openai import ChatOpenAI
from src import secret
from abi import logger

def create_model():
    """Create deepseek-r1 model for Data Engineer - NOT FUNCTIONAL YET"""
    logger.warning("🚧 deepseek-r1 model not functional yet - template only")
    
    api_key = secret.get('DEEPSEEK_API_KEY')
    if not api_key:
        logger.error("DEEPSEEK_API_KEY not found in environment")
        return None
    
    # Model configuration optimized for data engineer domain
    model = ChatOpenAI(
        model="deepseek-r1",
        api_key=api_key,
        temperature=0.1,  # Low temperature for professional accuracy
        max_tokens=4000,
        # Domain-specific optimizations would go here
    )
    
    return model

# Model instance - NOT FUNCTIONAL YET
model = None  # Would be: create_model()