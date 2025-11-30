from langchain_ollama import ChatOllama
from naas_abi_core.models.Model import ChatModel

MODEL_ID = "deepseek-r1:8b"
NAME = "DeepSeek R1 8B"
DESCRIPTION = "DeepSeek's R1 8B reasoning model for advanced problem-solving, mathematics, and logical analysis."
IMAGE = "https://naasai-public.s3.eu-west-3.amazonaws.com/logos/ollama_100x100.png"
CONTEXT_WINDOW = 32768
PROVIDER = "ollama"

model: ChatModel = ChatModel(
    model_id=MODEL_ID,
    name=NAME,
    description=DESCRIPTION,
    image=IMAGE,
    provider=PROVIDER,
    model=ChatOllama(
        model=MODEL_ID,
        temperature=0.1,  # Low temperature for precise reasoning
        # num_predict=4096,  # Max tokens for detailed explanations
    ),
    context_window=CONTEXT_WINDOW,
)
