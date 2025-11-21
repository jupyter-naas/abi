from lib.abi.models.Model import ChatModel
from langchain_ollama import ChatOllama

MODEL_ID = "qwen3:8b"
PROVIDER = "qwen"
NAME = "Qwen3 8B"
DESCRIPTION = "Alibaba's Qwen3 8B model for local deployment. Excellent at code generation, reasoning, and multilingual tasks."
IMAGE = "https://naasai-public.s3.eu-west-3.amazonaws.com/logos/ollama_100x100.png"
CONTEXT_WINDOW = 32768
PROVIDER = "alibaba"
TEMPERATURE = 0.3  # Slightly creative for code/reasoning tasks

model: ChatModel = ChatModel(
    model_id=MODEL_ID,
    provider=PROVIDER,
    name=NAME,
    description=DESCRIPTION,
    image=IMAGE,
    model=ChatOllama(
        model=MODEL_ID,
        temperature=TEMPERATURE,
    ),
    context_window=CONTEXT_WINDOW,
)