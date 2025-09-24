from lib.abi.models.Model import ChatModel
from langchain_xai import ChatXAI
from src import secret
from typing import Optional
from pydantic import SecretStr

NAME = "grok-4-latest"
ID = "grok-4-latest"
TEMPERATURE = 0.1
MAX_TOKENS = 4096
SEARCH_MODE = "auto"
MAX_SEARCH_RESULTS = 5
OWNER = "xai"
IMAGE = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTOv3K6RevHQCscoWPa2BvxKTq-9ygcQ4mhRA&s"
DESCRIPTION = "xAI's revolutionary AI with the highest intelligence scores globally, designed for truth-seeking and real-world understanding."
CONTEXT_WINDOW = 200000

model: Optional[ChatModel] = None

xai_api_key = secret.get("XAI_API_KEY")
model = ChatModel(
    model_id=ID,
    name=NAME,
    description=DESCRIPTION,
    image=IMAGE,
    owner=OWNER,
    context_window=CONTEXT_WINDOW,
    model=ChatXAI(
        model=ID,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        api_key=SecretStr(xai_api_key),
        # Enable Live Search for real-time information
        search_parameters={
            "mode": SEARCH_MODE,
            "max_search_results": MAX_SEARCH_RESULTS,
        },
    )
)