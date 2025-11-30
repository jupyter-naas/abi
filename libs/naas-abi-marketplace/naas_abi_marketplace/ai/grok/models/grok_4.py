from langchain_xai import ChatXAI
from naas_abi import secret
from naas_abi_core.models.Model import ChatModel
from pydantic import SecretStr

MODEL_ID = "grok-4"
NAME = "Grok 4"
TEMPERATURE = 0.1
MAX_TOKENS = 4096
SEARCH_MODE = "auto"
MAX_SEARCH_RESULTS = 5
PROVIDER = "xai"
IMAGE = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTOv3K6RevHQCscoWPa2BvxKTq-9ygcQ4mhRA&s"
DESCRIPTION = "xAI's revolutionary AI with the highest intelligence scores globally, designed for truth-seeking and real-world understanding."
CONTEXT_WINDOW = 200000

api_key = secret.get("XAI_API_KEY")
if secret.get("OPENROUTER_API_KEY"):
    api_key = secret.get("OPENROUTER_API_KEY")

model: ChatModel = ChatModel(
    model_id=MODEL_ID,
    name=NAME,
    description=DESCRIPTION,
    image=IMAGE,
    provider=PROVIDER,
    context_window=CONTEXT_WINDOW,
    model=ChatXAI(
        model=MODEL_ID,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        api_key=SecretStr(api_key),
        # Enable Live Search for real-time information
        search_parameters={
            "mode": SEARCH_MODE,
            "max_search_results": MAX_SEARCH_RESULTS,
        },
    ),
)
