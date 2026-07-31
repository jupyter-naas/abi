"""nomic-embed-text — the default local embedding model for a new project.

Every other embedding model in the marketplace is cloud-backed (OpenAI,
Bedrock), which meant a keyless project had no working vector store. This one
is served by the same local Ollama process as the chat model: 137M params,
~274MB on disk, 768-dimensional output, 8k context.
"""

from langchain_ollama import OllamaEmbeddings
from naas_abi_core.models.Model import (
    CanonicalModelId,
    EmbeddingModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.ollama import ABIModule
from naas_abi_marketplace.ai.ollama.defaults import DEFAULT_EMBEDDING_MODEL_TAG


class NomicEmbedTextModel(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.NOMIC_EMBED_TEXT
    MODEL_ID = DEFAULT_EMBEDDING_MODEL_TAG
    PROVIDER = ModelProvider.OLLAMA

    model: EmbeddingModel = EmbeddingModel(
        model_id=MODEL_ID,
        provider=PROVIDER,
        name="Nomic Embed Text",
        owner="nomic-ai",
        description=(
            "Nomic's open text embedding model running locally via Ollama. "
            "768 dimensions, 8k context, ~274MB — a keyless replacement for "
            "cloud embedding APIs."
        ),
        image="https://naasai-public.s3.eu-west-3.amazonaws.com/logos/ollama_100x100.png",
        dimensions=768,
        model=OllamaEmbeddings(
            model=MODEL_ID,
            base_url=ABIModule.resolved_base_url(),
        ),
    )


# Back-compat for direct importers.
model: EmbeddingModel = NomicEmbedTextModel.model
