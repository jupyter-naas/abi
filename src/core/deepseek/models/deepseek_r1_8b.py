from abi.models.Model import ChatModel
from langchain_ollama import ChatOllama
from typing import Optional
from abi import logger

ID = "deepseek-r1:8b"
NAME = "DeepSeek R1 8B"
DESCRIPTION = "DeepSeek's R1 8B reasoning model for advanced problem-solving, mathematics, and logical analysis."
IMAGE = "https://naasai-public.s3.eu-west-3.amazonaws.com/logos/ollama_100x100.png"
CONTEXT_WINDOW = 32768
OWNER = "ollama"

model: Optional[ChatModel] = None
model = ChatModel(
    model_id=ID,
    name=NAME,
    description=DESCRIPTION,
    image=IMAGE,
    owner=OWNER,
    model=ChatOllama(
        model=ID,
        temperature=0.1,  # Low temperature for precise reasoning
        # num_predict=4096,  # Max tokens for detailed explanations
    ),
    context_window=CONTEXT_WINDOW,
)