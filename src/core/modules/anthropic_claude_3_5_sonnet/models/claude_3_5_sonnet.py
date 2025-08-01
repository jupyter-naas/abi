from lib.abi.models.Model import ChatModel
from langchain_anthropic import ChatAnthropic
from src import secret
import os

ID = "claude-3-5-sonnet-20241022"
NAME = "claude-3-5-sonnet"
DESCRIPTION = "Anthropic's most intelligent model, with best-in-class performance for most tasks including complex reasoning and analysis."
IMAGE = "https://assets.anthropic.com/m/0edc05fa8e30f2f9/original/Anthropic_Glyph_Black.svg"
CONTEXT_WINDOW = 200000
OWNER = "anthropic"

if "ANTHROPIC_API_KEY" not in os.environ:
    os.environ["ANTHROPIC_API_KEY"] = secret.get("ANTHROPIC_API_KEY", "")

model = ChatModel(
    model_id=ID,
    name=NAME,
    description=DESCRIPTION,
    image=IMAGE,
    owner=OWNER,
    model=ChatAnthropic(
        model_name=ID,
        temperature=0,
        max_tokens_to_sample=4096,
        timeout=None,
        max_retries=2,
        stop=None,
    ),
    context_window=CONTEXT_WINDOW,
) 