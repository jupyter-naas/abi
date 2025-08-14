from abi.models.Model import ChatModel
from langchain_ollama import ChatOllama
from typing import Optional
from abi import logger

ID = "gemma3:4b"
NAME = "Gemma3 4B"
DESCRIPTION = "Google's open-source Gemma3 4B model for local deployment. Fast, lightweight alternative to cloud Gemini."
IMAGE = "https://naasai-public.s3.eu-west-3.amazonaws.com/logos/ollama_100x100.png"
CONTEXT_WINDOW = 8192
OWNER = "ollama"

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
            temperature=0.4,  # Balanced creativity for general conversation
            # num_predict=2048,  # Reasonable output length for 4B model
        ),
        context_window=CONTEXT_WINDOW,
    )
    logger.debug("✅ Gemma3 4B model loaded successfully via Ollama")
except Exception as e:
    logger.error(f"⚠️  Error loading Gemma3 4B model: {e}")
    logger.error("   Make sure Ollama is running and 'gemma3:4b' model is pulled.")