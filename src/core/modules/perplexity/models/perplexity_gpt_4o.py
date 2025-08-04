from lib.abi.models.Model import ChatModel
from langchain_openai import ChatOpenAI
from src import secret
from typing import Optional
from pydantic import SecretStr

ID = "gpt-4o"
NAME = "perplexity-gpt-4o"
DESCRIPTION = "GPT-4o model used for Perplexity AI agent with real-time web search capabilities."
IMAGE = "https://images.seeklogo.com/logo-png/61/1/perplexity-ai-icon-black-logo-png_seeklogo-611679.png"
CONTEXT_WINDOW = 128000
OWNER = "openai"

model: Optional[ChatModel] = None
if secret.get("OPENAI_API_KEY"):
    model = ChatModel(
        model_id=ID,
        name=NAME,
        description=DESCRIPTION,
        image=IMAGE,
        owner=OWNER,
        model=ChatOpenAI(
            model=ID,
            temperature=0,
            api_key=SecretStr(secret.get('OPENAI_API_KEY'))
        ),
        context_window=CONTEXT_WINDOW,
    )