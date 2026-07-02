from langchain_openai import OpenAIEmbeddings
from naas_abi_core.models.Model import (
    CanonicalModelId,
    EmbeddingModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.openrouter import ABIModule
from pydantic import SecretStr

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class TextEmbeddingAda002Model(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.TEXT_EMBEDDING_ADA_002
    MODEL_ID = "openai/text-embedding-ada-002"
    PROVIDER = ModelProvider.OPENROUTER

    model: EmbeddingModel = EmbeddingModel(
        model_id=MODEL_ID,
        provider=PROVIDER,
        model=OpenAIEmbeddings(
            model=MODEL_ID,
            api_key=SecretStr(ABIModule.get_instance().configuration.openrouter_api_key),
            base_url=OPENROUTER_BASE_URL,
        ),
    )


model: EmbeddingModel = TextEmbeddingAda002Model.model
