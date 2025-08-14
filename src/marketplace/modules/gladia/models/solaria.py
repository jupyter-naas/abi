from lib.abi.models.Model import ChatModel
from langchain_openai import ChatOpenAI
from typing import Optional
from abi import logger
from src import secret
from pydantic import SecretStr

try:
    from langchain_ollama import ChatOllama
except ImportError:
    ChatOllama = None

ID = "gpt-4o-mini"
NAME = "Gladia Solaria Agent Model"
DESCRIPTION = "OpenAI model optimized for Gladia speech-to-text agent interactions with fast response times and accuracy."
IMAGE = "https://assets-global.website-files.com/64b43dcce44f4a76d6e1c5b4/64b43dcce44f4a76d6e1c676_favicon.png"
CONTEXT_WINDOW = 128000
OWNER = "openai"

model: Optional[ChatModel] = None
openai_api_key = secret.get("OPENAI_API_KEY")
if openai_api_key:
    model = ChatModel(
        model_id=ID,
        name=NAME,
        description=DESCRIPTION,
        image=IMAGE,
        owner=OWNER,
        model=ChatOpenAI(
            model=ID,
            temperature=0.1,
            api_key=SecretStr(openai_api_key),
        ),
        context_window=CONTEXT_WINDOW,
    )
else:
    if ChatOllama is not None:
        try:
            model = ChatModel(
                model_id='qwen3:8b',
                name="Gladia Qwen3-8b",
                description="Qwen3 8B parameter model running locally via Ollama for Gladia speech-to-text operations.",
                image=IMAGE,
                owner="alibaba",
                model=ChatOllama(
                    model='qwen3:8b',
                    temperature=0.1,
                ),
                context_window=32768,
            )
        except Exception as e:
            logger.error(f"Qwen3 8B model not available for Gladia agent - {e}")
    else:
        logger.warning("No ChatModel available - both OpenAI and Ollama unavailable")