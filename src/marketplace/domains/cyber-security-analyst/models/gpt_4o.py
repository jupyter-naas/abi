"""
GPT-4o model configuration for Cyber Security Analyst domain expert
Optimized for cyber security intelligence and D3FEND analysis
"""

from langchain_openai import ChatOpenAI
import os
from abi import logger

def create_model():
    """Create gpt-4o model optimized for cyber security analysis"""
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        logger.warning("OPENAI_API_KEY not found - model will not be available")
        return None
    
    try:
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
        
        logger.info("✅ GPT-4o model configured for cyber security analysis")
        return model
        
    except Exception as e:
        logger.error(f"❌ Failed to create GPT-4o model: {e}")
        return None

def get_model():
    """Get the configured model instance"""
    return create_model()

# Export for easy import
__all__ = ['create_model', 'get_model']
