from lib.abi.models.Model import ChatModel
from langchain_openai import ChatOpenAI
from src import secret
from typing import Optional

ID = "meta-llama/Llama-3.3-70B-Instruct"
NAME = "llama-3.3-70b-instruct"
DESCRIPTION = "Meta's latest Llama model with 70B parameters, optimized for instruction-following and conversational dialogue."
IMAGE = "https://github.com/meta-llama/llama/raw/main/Llama_Repo.jpeg"
CONTEXT_WINDOW = 131072
OWNER = "meta"

model: Optional[ChatModel] = None
if secret.get("OPENAI_API_KEY"):
    model = ChatModel(
        model_id=ID,
        name=NAME,
        description=DESCRIPTION,
        image=IMAGE,
        owner=OWNER,
        model=ChatOpenAI(
            model=NAME,
            temperature=0,
            max_completion_tokens=4096,
            timeout=None,
            max_retries=2,
            # Note: This assumes an OpenAI-compatible endpoint for Llama
            # You may need to configure base_url for specific providers
        ),
        context_window=CONTEXT_WINDOW,
    ) 