from langchain_mistralai import ChatMistralAI
from naas_abi_marketplace.ai.mistral import ABIModule
from naas_abi_core.models.Model import ChatModel
from pydantic import SecretStr

MODEL_ID = "mistral-large-2411"
PROVIDER = "mistral"
TEMPERATURE = 0

model: ChatModel = ChatModel(
    model_id=MODEL_ID,
    provider=PROVIDER,
    model=ChatMistralAI(
        model_name=MODEL_ID,
        temperature=TEMPERATURE,
        api_key=SecretStr(ABIModule.get_instance().configuration.mistral_api_key),
    ),
)
