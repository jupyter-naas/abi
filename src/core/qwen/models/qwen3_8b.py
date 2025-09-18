from abi.models.Model import ChatModel
from typing import Optional
from langchain_ollama import ChatOllama
from abi import logger

ID = "qwen3:8b"
NAME = "Qwen3 8B"
DESCRIPTION = "Alibaba's Qwen3 8B model for local deployment. Excellent at code generation, reasoning, and multilingual tasks."
IMAGE = "https://naasai-public.s3.eu-west-3.amazonaws.com/logos/ollama_100x100.png"
CONTEXT_WINDOW = 32768
OWNER = "ollama"
TEMPERATURE = 0.3 # Slightly creative for code/reasoning tasks

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
            temperature=TEMPERATURE,  
        ),
        context_window=CONTEXT_WINDOW,
    )
    logger.debug("✅ Qwen3 8B model loaded successfully via Ollama")
except Exception as e:
    logger.error(f"⚠️  Error loading Qwen3 8B model: {e}")
    logger.error("   Make sure Ollama is running and 'qwen3:8b' model is pulled.")