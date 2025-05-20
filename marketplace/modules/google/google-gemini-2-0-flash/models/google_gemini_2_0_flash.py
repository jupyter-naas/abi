from lib.abi.models.Model import ChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from src import secret
import os

ID = "113f2201-9f0e-4bf1-a25f-3ea8ba88e41d"
NAME = "gemini-2.0-flash"
DESCRIPTION = "Google's most advanced, multimodal flagship model that's cheaper and faster than GPT-4 Turbo."
IMAGE = "https://naasai-public.s3.eu-west-3.amazonaws.com/logos/google_100x100.png"
CONTEXT_WINDOW = 128000
OWNER = "google" 


if "GOOGLE_API_KEY" not in os.environ:
    os.environ["GOOGLE_API_KEY"] = secret.get("GOOGLE_API_KEY", '')

model = ChatModel(
    model_id=ID,
    name=NAME,
    description=DESCRIPTION,
    image=IMAGE,
    owner=OWNER,
    model=ChatGoogleGenerativeAI(
        model=NAME,
        temperature=0,
        max_tokens=None,
        timeout=None,
        max_retries=2,
    ),
    context_window=CONTEXT_WINDOW
)