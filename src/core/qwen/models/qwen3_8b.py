from abi.models.Model import ChatModel
from langchain_ollama import ChatOllama

ID = "qwen3:8b"
NAME = "Qwen3 8B"
DESCRIPTION = "Alibaba's Qwen3 8B model for local deployment. Excellent at code generation, reasoning, and multilingual tasks."
IMAGE = "https://naasai-public.s3.eu-west-3.amazonaws.com/logos/ollama_100x100.png"
CONTEXT_WINDOW = 32768
OWNER = "ollama"
TEMPERATURE = 0.3 # Slightly creative for code/reasoning tasks

model: ChatModel = ChatModel(
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