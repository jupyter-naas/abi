from langchain_google_genai import ChatGoogleGenerativeAI  # type: ignore
from naas_abi_core.models.Model import ChatModel
from naas_abi_marketplace.ai.gemini import ABIModule
from pydantic import SecretStr

MODEL_ID = "gemini-2.5-flash"
PROVIDER = "google"


model: ChatModel = ChatModel(
    model_id=MODEL_ID,
    provider=PROVIDER,
    model=ChatGoogleGenerativeAI(
        model=MODEL_ID,
        api_key=SecretStr(
            ABIModule.get_instance().configuration.gemini_api_key
        ),
    ),
)
