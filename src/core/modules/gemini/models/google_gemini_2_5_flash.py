from lib.abi.models.Model import ChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from src import secret
import os

ID = "google-gemini-2-5-flash"
NAME = "gemini-2.5-flash"
DESCRIPTION = "Google's best model in terms of price-performance with image generation capabilities, offering well-rounded capabilities including image generation."
IMAGE = "https://naasai-public.s3.eu-west-3.amazonaws.com/logos/google_100x100.png"
CONTEXT_WINDOW = 1048576  # 1M token context window
OWNER = "google"
TEMPERATURE = 1.0

if "GOOGLE_API_KEY" not in os.environ:
    os.environ["GOOGLE_API_KEY"] = secret.get("GOOGLE_API_KEY", "")

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
        google_api_key=secret.get("GOOGLE_API_KEY", ""),
    ),
    context_window=CONTEXT_WINDOW,
)