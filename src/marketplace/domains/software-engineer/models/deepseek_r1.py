"""
🚧 NOT FUNCTIONAL YET - Model Configuration Template
DeepSeek R1 model configuration for Software Engineer domain expert
"""

from langchain_openai import ChatOpenAI
from src import secret
from abi import logger

def create_model():
    """Create DeepSeek R1 model for Software Engineer - NOT FUNCTIONAL YET"""
    logger.warning("🚧 DeepSeek R1 model not functional yet - template only")
    
    # Template configuration - would need actual DeepSeek API integration
    api_key = secret.get('DEEPSEEK_API_KEY')
    if not api_key:
        logger.error("DEEPSEEK_API_KEY not found in environment")
        return None
    
    # Placeholder - actual implementation would use DeepSeek client
    model = ChatOpenAI(
        model="deepseek-r1",  # Placeholder model name
        api_key=api_key,
        temperature=0,
        max_tokens=4000,
        # DeepSeek-specific parameters would go here
    )
    
    return model

# Model instance - NOT FUNCTIONAL YET
model = None  # Would be: create_model()
