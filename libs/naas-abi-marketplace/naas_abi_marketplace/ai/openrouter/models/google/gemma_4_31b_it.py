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


class Gemma431BItModel(ModelDefinition):
    """Gemma 4 31B — the dense sibling of ``gemma-4-26b-a4b-it``. Stronger per
    token and slightly pricier; swap the model registry defaults to this
    canonical id when a generated project needs more headroom.
    """

    CANONICAL_ID = CanonicalModelId.GEMMA_4_31B_IT
    MODEL_ID = "google/gemma-4-31b-it"
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


model: ChatModel = Gemma431BItModel.model
