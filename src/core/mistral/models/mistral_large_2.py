from lib.abi.models.Model import ChatModel
from langchain_mistralai import ChatMistralAI
from src import secret
from pydantic import SecretStr

ID = "mistral-large-2407"
NAME = "mistral-large-2"
DESCRIPTION = "Mistral's flagship model with enhanced code generation, mathematics, and reasoning capabilities."
IMAGE = "https://mistral.ai/images/logo_hubc88c4ece131262e7906a8bf7ae79de9f_1864_256x0_resize_q90_h2_lanczos_3.webp"
CONTEXT_WINDOW = 128000
OWNER = "mistral"
TEMPERATURE = 0
MAX_TOKENS = 4096
MAX_RETRIES = 2

mistral_api_key = secret.get("MISTRAL_API_KEY")
model: ChatModel = ChatModel(
    model_id=ID,
    name=NAME,
    description=DESCRIPTION,
    image=IMAGE,
    owner=OWNER,
    model=ChatMistralAI(
        model_name=ID,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        max_retries=MAX_RETRIES,
        api_key=SecretStr(mistral_api_key),
    ),
    context_window=CONTEXT_WINDOW,
)