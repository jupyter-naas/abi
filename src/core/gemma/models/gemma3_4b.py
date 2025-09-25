from abi.models.Model import ChatModel
from langchain_ollama import ChatOllama

ID = "gemma3:4b"
NAME = "Gemma3 4B"
DESCRIPTION = "Google's open-source Gemma3 4B model for local deployment. Fast, lightweight alternative to cloud Gemini."
IMAGE = "https://naasai-public.s3.eu-west-3.amazonaws.com/logos/ollama_100x100.png"
CONTEXT_WINDOW = 8192
OWNER = "ollama"

model: ChatModel = ChatModel(
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