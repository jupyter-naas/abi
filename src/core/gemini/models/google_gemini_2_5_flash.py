from lib.abi.models.Model import ChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from src import secret
from pydantic import SecretStr

MODEL_ID = "gemini-2.5-flash"
NAME = "gemini-2.5-flash"
DESCRIPTION = "Google's best model in terms of price-performance with image generation capabilities, offering well-rounded capabilities including image generation."
IMAGE = "https://naasai-public.s3.eu-west-3.amazonaws.com/logos/google_100x100.png"
CONTEXT_WINDOW = 1048576  # 1M token context window
PROVIDER = "google"

model: ChatModel = ChatModel(
    model_id=MODEL_ID,
    name=NAME,
    description=DESCRIPTION,
    image=IMAGE,
    provider=PROVIDER,
    model=ChatGoogleGenerativeAI(
        model=NAME,
        temperature=1.0,
        max_tokens=None,
        timeout=None,
        max_retries=2,
        api_key=SecretStr(secret.get("GOOGLE_API_KEY")),
    ),
    context_window=CONTEXT_WINDOW,
)