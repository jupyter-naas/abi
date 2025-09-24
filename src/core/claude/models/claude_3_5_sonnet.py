from lib.abi.models.Model import ChatModel
from langchain_anthropic import ChatAnthropic
from src import secret
from pydantic import SecretStr
from typing import Optional

ID = "claude-3-5-sonnet-20241022"
NAME = "claude-3-5-sonnet"
DESCRIPTION = "Anthropic's most intelligent model, with best-in-class performance for most tasks including complex reasoning and analysis."
IMAGE = "https://assets.anthropic.com/m/0edc05fa8e30f2f9/original/Anthropic_Glyph_Black.svg"
CONTEXT_WINDOW = 200000
OWNER = "anthropic"
TEMPERATURE = 0
MAX_TOKENS = 4096
MAX_RETRIES = 2

model: Optional[ChatModel] = None
anthropic_api_key = secret.get("ANTHROPIC_API_KEY")
model = ChatModel(
    model_id=ID,
    name=NAME,
    description=DESCRIPTION,
    image=IMAGE,
    owner=OWNER,
    model=ChatAnthropic(
        model_name=ID,
        temperature=TEMPERATURE,
        max_tokens_to_sample=MAX_TOKENS,
        timeout=None,
        max_retries=MAX_RETRIES,
        stop=None,
        api_key=SecretStr(anthropic_api_key),
    ),
    context_window=CONTEXT_WINDOW,
) 