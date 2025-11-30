from langchain_ollama import ChatOllama
from naas_abi_core.models.Model import ChatModel

ID = "gemma3:4b"
NAME = "Gemma3 4B"
DESCRIPTION = "Google's open-source Gemma3 4B model for local deployment. Fast, lightweight alternative to cloud Gemini."
IMAGE = "https://naasai-public.s3.eu-west-3.amazonaws.com/logos/ollama_100x100.png"
CONTEXT_WINDOW = 8192
PROVIDER = "ollama"

model: ChatModel = ChatModel(
    model_id=ID,
    name=NAME,
    description=DESCRIPTION,
    image=IMAGE,
    provider=PROVIDER,
    model=ChatOllama(
        model=ID,
        temperature=0.4,  # Balanced creativity for general conversation
        # num_predict=2048,  # Reasonable output length for 4B model
    ),
    context_window=CONTEXT_WINDOW,
)
