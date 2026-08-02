"""nomic-embed-text — the default local embedding model for a new project.

Every other embedding model in the marketplace is cloud-backed (OpenAI,
Bedrock), which meant a keyless project had no working vector store. This one
is served by the same local Ollama process as the chat model: 137M params,
~274MB on disk, 768-dimensional output.

**Input is capped at 2048 tokens and anything beyond it is dropped silently.**
Ollama reports ``nomic-bert.context_length = 2048``, and raising ``num_ctx``
does not lift it — the model truncates and returns a normal-looking vector.
Measured: two ~3000-word documents differing only in their final sentence embed
to a cosine similarity of exactly 1.0, while the same two tails inside the limit
give 0.868. So chunk before embedding; a whole document handed to this model is
indexed by its opening only. (The 8192 figure on Nomic's model card is the
RoPE-scaled maximum, which the Ollama build does not expose.)
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
            "768 dimensions, 2048-token input limit, ~274MB — a keyless "
            "replacement for "
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
