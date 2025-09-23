"""
GPT-4o model configuration for Cyber Security Analyst domain expert
Following ABI model pattern exactly
"""

from langchain_openai import ChatOpenAI
from pydantic import SecretStr
from src import secret
from abi import logger
from typing import Optional

ID = "gpt-4o"
NAME = "gpt-4o"
DESCRIPTION = "GPT-4o optimized for cyber security intelligence and D3FEND analysis"

model: Optional[ChatOpenAI] = None
openai_api_key = secret.get("OPENAI_API_KEY")
if openai_api_key:
    model = ChatOpenAI(
        model=ID,
        temperature=0,
        api_key=SecretStr(openai_api_key),
    )
    logger.info("✅ GPT-4o model configured for cyber security analysis")
else:
    logger.warning("OPENAI_API_KEY not found - GPT-4o model will not be available")

def create_model():
    """Create gpt-4o model optimized for cyber security analysis"""
    return model

def get_model():
    """Get the configured model instance"""
    return model

__all__ = ['create_model', 'get_model', 'model']