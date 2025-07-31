from lib.abi.models.Model import ChatModel
from langchain_mistralai import ChatMistralAI
from src import secret
import os

ID = "mistral-large-2407"
NAME = "mistral-large-2"
DESCRIPTION = "Mistral's flagship model with enhanced code generation, mathematics, and reasoning capabilities."
IMAGE = "https://mistral.ai/images/logo_hubc88c4ece131262e7906a8bf7ae79de9f_1864_256x0_resize_q90_h2_lanczos_3.webp"
CONTEXT_WINDOW = 128000
OWNER = "mistral"

if "MISTRAL_API_KEY" not in os.environ:
    os.environ["MISTRAL_API_KEY"] = secret.get("MISTRAL_API_KEY", "")

model = ChatModel(
    model_id=ID,
    name=NAME,
    description=DESCRIPTION,
    image=IMAGE,
    owner=OWNER,
    model=ChatMistralAI(
        model=ID,
        temperature=0,
        max_tokens=4096,
        max_retries=2,
    ),
    context_window=CONTEXT_WINDOW,
) 