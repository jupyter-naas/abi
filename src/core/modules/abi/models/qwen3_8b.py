from lib.abi.models.Model import ChatModel
from langchain_ollama import ChatOllama
from typing import Optional
from abi import logger

ID = "qwen3:8b"
NAME = "qwen3-8b"
DESCRIPTION = "Qwen3 8B parameter model running locally via Ollama for privacy-focused multi-agent orchestration."
IMAGE = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
CONTEXT_WINDOW = 32768
OWNER = "alibaba"

model: Optional[ChatModel] = None
try:
    model = ChatModel(
        model_id=ID,
        name=NAME,
        description=DESCRIPTION,
        image=IMAGE,
        owner=OWNER,
        model=ChatOllama(
            model=ID,
            temperature=0.7,  # Lower temperature for local model stability
        ),
        context_window=CONTEXT_WINDOW,
    )
    logger.debug("✅ Abi Agent: Qwen3 8B model loaded successfully via Ollama")
except Exception as e:
    logger.error(f"Abi Agent: Qwen3 8B model not available - {e}")
    logger.error("   Make sure Ollama is running and 'qwen3:8b' model is pulled.")