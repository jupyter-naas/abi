from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from lib.abi.models.Model import ChatModel
from src.core.chatgpt import ABIModule

MODEL_ID = "o4-mini-deep-research"
PROVIDER = "openai"

model: ChatModel = ChatModel(
    model_id=MODEL_ID,
    provider=PROVIDER,
    model=ChatOpenAI(
        model=MODEL_ID,
        temperature=0,
        api_key=SecretStr(
            ABIModule.get_instance().configuration.openrouter_api_key
            or ABIModule.get_instance().configuration.openai_api_key
        ),
    ),
)
