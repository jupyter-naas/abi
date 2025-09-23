"""
🚧 NOT FUNCTIONAL YET - Model Configuration Template
gpt-4o model configuration for Cyber Security Analyst domain expert
"""

from langchain_openai import ChatOpenAI
from src import secret
from abi import logger

def create_model():
    """Create gpt-4o model for Cyber Security Analyst - NOT FUNCTIONAL YET"""
    logger.warning("🚧 gpt-4o model not functional yet - template only")
    
    api_key = secret.get('OPENAI_API_KEY')
    if not api_key:
        logger.error("OPENAI_API_KEY not found in environment")
        return None
    
    # Model configuration optimized for cyber security analyst domain
    model = ChatOpenAI(
        model="gpt-4o",
        api_key=api_key,
        temperature=0.0,  # Zero temperature for security precision
        max_tokens=4000,
        # Cyber security specific optimizations
        model_kwargs={
            "frequency_penalty": 0.1,  # Reduce repetition in security analysis
            "presence_penalty": 0.1,   # Encourage comprehensive coverage
        }
    )
    
    return model

# Model instance - NOT FUNCTIONAL YET
model = None  # Would be: create_model()
