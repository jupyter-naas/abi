from lib.abi.models.Model import ChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from src import secret
from pydantic import SecretStr
from abi import logger
from typing import Optional

ID = "113f2201-9f0e-4bf1-a25f-3ea8ba88e41d"
NAME = "gemini-2.0-flash"
DESCRIPTION = "Google's most advanced, multimodal flagship model with enhanced reasoning capabilities, cheaper and faster than GPT-4 Turbo."
IMAGE = "https://naasai-public.s3.eu-west-3.amazonaws.com/logos/google_100x100.png"
CONTEXT_WINDOW = 1000000  # Updated to 1M token context window
OWNER = "google"
TEMPERATURE = 0.7

model: Optional[ChatModel] = None

google_api_key = secret.get("GOOGLE_API_KEY")
model = ChatModel(
    model_id=ID,
    name=NAME,
    description=DESCRIPTION,
    image=IMAGE,
    owner=OWNER,
    model=ChatGoogleGenerativeAI(
        model=NAME,
        temperature=TEMPERATURE,
        max_tokens=None,
        timeout=None,
        max_retries=2,
        api_key=SecretStr(google_api_key),
    ),
    context_window=CONTEXT_WINDOW,
)