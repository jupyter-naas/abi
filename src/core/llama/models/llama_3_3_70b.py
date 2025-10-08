from abi.models.Model import ChatModel
from langchain_ollama import ChatOllama

ID = "meta-llama/Llama-3.3-70B-Instruct"
NAME = "llama-3.3-70b-instruct"
DESCRIPTION = "Meta's latest Llama model with 70B parameters, optimized for instruction-following and conversational dialogue."
IMAGE = "https://github.com/meta-llama/llama/raw/main/Llama_Repo.jpeg"
CONTEXT_WINDOW = 131072
OWNER = "meta"
TEMPERATURE = 0
MAX_TOKENS = 4096
MAX_RETRIES = 2

model: ChatModel = ChatModel(
    model_id=ID,
    name=NAME,
    description=DESCRIPTION,
    image=IMAGE,
    owner=OWNER,
    model=ChatOllama(
        model=NAME,
        temperature=TEMPERATURE,
    ),
    context_window=CONTEXT_WINDOW,
) 