from lib.abi.models.Model import ChatModel
from langchain_mistralai import ChatMistralAI
from src import secret
from pydantic import SecretStr

MODEL_ID = "mistral-small-2506"
PROVIDER = "mistral"
TEMPERATURE = 0

model: ChatModel = ChatModel(
    model_id=MODEL_ID,
    provider=PROVIDER,
    model=ChatMistralAI(
        model_name=MODEL_ID,
        temperature=TEMPERATURE,
        api_key=SecretStr(secret.get("MISTRAL_API_KEY")),
    ),
)

