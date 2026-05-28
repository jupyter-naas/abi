from langchain_openai import OpenAIEmbeddings
from naas_abi_core.models.Model import (
    CanonicalModelId,
    EmbeddingModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.chatgpt import ABIModule
from pydantic import SecretStr


class TextEmbedding3LargeModel(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.TEXT_EMBEDDING_3_LARGE
    MODEL_ID = "text-embedding-3-large"
    PROVIDER = ModelProvider.OPENAI

    model: EmbeddingModel = EmbeddingModel(
        model_id=MODEL_ID,
        provider=PROVIDER,
        model=OpenAIEmbeddings(
            model=MODEL_ID,
            api_key=SecretStr(ABIModule.get_instance().configuration.openai_api_key),
        ),
    )


# Back-compat for direct importers.
model: EmbeddingModel = TextEmbedding3LargeModel.model
