from lib.abi.models.Model import ChatModel
from src import secret
import os

ID = "google-gemini-image-generation"
NAME = "gemini-2.0-flash-preview-image-generation"
DESCRIPTION = "Google Gemini 2.0 Flash with TRUE image generation capabilities using official SDK."
IMAGE = "https://naasai-public.s3.eu-west-3.amazonaws.com/logos/google_100x100.png"
CONTEXT_WINDOW = 32768
OWNER = "google"
TEMPERATURE = 1.0

# Direct Google Gen AI SDK - no LangChain wrapper
if "GOOGLE_API_KEY" not in os.environ:
    os.environ["GOOGLE_API_KEY"] = secret.get("GOOGLE_API_KEY", "")

# This will be a direct client, not a LangChain model
model = ChatModel(
    model_id=ID,
    name=NAME,
    description=DESCRIPTION,
    image=IMAGE,
    owner=OWNER,
    model=None,  # We'll use direct SDK calls
    context_window=CONTEXT_WINDOW,
    temperature=TEMPERATURE,
)