from langchain_mistralai import ChatMistralAI
from naas_abi import secret
from naas_abi_core.models.Model import ChatModel
from pydantic import SecretStr

MODEL_ID = "mistral-small-2506"
PROVIDER = "mistral"
TEMPERATURE = 0

api_key = secret.get("MISTRAL_API_KEY")
if secret.get("OPENROUTER_API_KEY"):
    api_key = secret.get("OPENROUTER_API_KEY")

model: ChatModel = ChatModel(
    model_id=MODEL_ID,
    provider=PROVIDER,
    model=ChatMistralAI(
        model_name=MODEL_ID,
        temperature=TEMPERATURE,
        api_key=SecretStr(api_key),
    ),
)
