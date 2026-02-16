from langchain_openai import ChatOpenAI
from naas_abi_core.models.Model import ChatModel
from naas_abi_marketplace.ai.chatgpt import ABIModule
from pydantic import SecretStr

MODEL_ID = "gpt-5-nano"
PROVIDER = "openai"

model: ChatModel = ChatModel(
    model_id=MODEL_ID,
    provider=PROVIDER,
    model=ChatOpenAI(
        model=MODEL_ID,
        temperature=0,
        api_key=SecretStr(ABIModule.get_instance().configuration.openai_api_key),
    ),
)
