from langchain_openai import ChatOpenAI
from naas_abi_core.models.Model import (
    CanonicalModelId,
    ChatModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.chatgpt import ABIModule
from pydantic import SecretStr


class Gpt41Model(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.GPT_4_1
    MODEL_ID = "gpt-4.1"
    PROVIDER = ModelProvider.OPENAI

    model: ChatModel = ChatModel(
        model_id=MODEL_ID,
        provider=PROVIDER,
        model=ChatOpenAI(
            model=MODEL_ID,
            temperature=0,
            timeout=180,
            max_retries=3,
            api_key=SecretStr(ABIModule.get_instance().configuration.openai_api_key),
        ),
    )


model: ChatModel = Gpt41Model.model
