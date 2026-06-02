from langchain_openai import ChatOpenAI
from naas_abi_core.models.Model import (
    CanonicalModelId,
    ChatModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.chatgpt import ABIModule
from pydantic import SecretStr


class O3DeepResearchModel(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.O3_DEEP_RESEARCH
    MODEL_ID = "o3-deep-research"
    PROVIDER = ModelProvider.OPENAI

    model: ChatModel = ChatModel(
        model_id=MODEL_ID,
        provider=PROVIDER,
        model=ChatOpenAI(
            model=MODEL_ID,
            temperature=0,
            api_key=SecretStr(ABIModule.get_instance().configuration.openai_api_key),
        ),
    )


model: ChatModel = O3DeepResearchModel.model
