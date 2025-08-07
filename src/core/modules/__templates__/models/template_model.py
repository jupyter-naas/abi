from lib.abi.models.Model import ChatModel
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from typing import Optional
from abi import logger
from src import secret
from pydantic import SecretStr

ID = "gpt-4o"
NAME = "gpt-4o"
DESCRIPTION = "OpenAI's most advanced model with superior performance across text, code, and reasoning tasks."
IMAGE = "https://i.pinimg.com/736x/2a/62/c3/2a62c34e0d217a7aa14645ce114d84b3.jpg"
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
            temperature=0,
            api_key=SecretStr(openai_api_key),
        ),
        context_window=CONTEXT_WINDOW,
    )
else:
    try:
        model = ChatModel(
            model_id='qwen3:8b',
            name="qwen3-8b",
            description="Qwen3 8B parameter model running locally via Ollama for privacy-focused multi-agent orchestration.",
            image="https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png",
            owner="alibaba",
            model=ChatOllama(
                model='qwen3:8b',
                temperature=0.7,  # Lower temperature for local model stability
            ),
            context_window=32768,
        )
    except Exception as e:
        logger.error(f"Qwen3 8B model not available - {e}")