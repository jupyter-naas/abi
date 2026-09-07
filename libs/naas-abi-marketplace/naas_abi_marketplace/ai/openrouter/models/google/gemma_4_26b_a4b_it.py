from langchain_openai import ChatOpenAI
from naas_abi_core.models.Model import (
    CanonicalModelId,
    ChatModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.openrouter import ABIModule
from pydantic import SecretStr

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class Gemma426BA4BItModel(ModelDefinition):
    """Gemma 4 26B-A4B — a sparse mixture-of-experts with only 4B active
    parameters, so it prices and responds like a small model while reading a
    262k context. Tool calling is supported, which is why it can back both
    plain chat and the tool-binding agents in a generated project.
    """

    CANONICAL_ID = CanonicalModelId.GEMMA_4_26B_A4B_IT
    MODEL_ID = "google/gemma-4-26b-a4b-it"
    PROVIDER = ModelProvider.OPENROUTER

    model: ChatModel = ChatModel(
        model_id=MODEL_ID,
        provider=PROVIDER,
        model=ChatOpenAI(
            model=MODEL_ID,
            temperature=0,
            timeout=120,
            max_retries=3,
            api_key=SecretStr(ABIModule.get_instance().configuration.openrouter_api_key),
            base_url=OPENROUTER_BASE_URL,
        ),
    )


model: ChatModel = Gemma426BA4BItModel.model
