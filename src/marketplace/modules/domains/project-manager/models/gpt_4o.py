"""
🚧 NOT FUNCTIONAL YET - Model Configuration Template
GPT-4o model configuration for Project Manager domain expert
"""

from langchain_openai import ChatOpenAI
from src import secret
from abi import logger

def create_model():
    """Create GPT-4o model for Project Manager - NOT FUNCTIONAL YET"""
    logger.warning("🚧 GPT-4o model not functional yet - template only")
    
    api_key = secret.get('OPENAI_API_KEY')
    if not api_key:
        logger.error("OPENAI_API_KEY not found in environment")
        return None
    
    model = ChatOpenAI(
        model="gpt-4o",
        api_key=api_key,
        temperature=0,
        max_tokens=4000,
        # Project management optimized parameters
        frequency_penalty=0.1,  # Reduce repetition in project plans
        presence_penalty=0.1,   # Encourage diverse solution approaches
    )
    
    return model

# Model instance - NOT FUNCTIONAL YET
model = None  # Would be: create_model()
