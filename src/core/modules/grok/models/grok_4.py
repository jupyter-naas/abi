from lib.abi.models.Model import ChatModel
from langchain_xai import ChatXAI
from src import secret
from typing import Optional
from pydantic import SecretStr
from abi import logger

NAME = "grok-4-latest"
ID = "grok-4-latest"
TEMPERATURE = 0.1
MAX_TOKENS = 4096
SEARCH_MODE = "auto"
MAX_SEARCH_RESULTS = 5

model: Optional[ChatModel] = None

xai_api_key = secret.get("XAI_API_KEY")
if xai_api_key:
    model = ChatXAI(
        model=ID,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        api_key=SecretStr(xai_api_key),
        # Enable Live Search for real-time information
        search_parameters={
            "mode": SEARCH_MODE,
            "max_search_results": MAX_SEARCH_RESULTS,
        },
    )
    logger.debug("✅ Using xAI Grok with langchain-xai integration")
else:
    logger.error("XAI_API_KEY not found")