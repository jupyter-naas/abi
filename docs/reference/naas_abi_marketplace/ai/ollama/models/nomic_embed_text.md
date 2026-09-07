# NomicEmbedTextModel

## What it is
- A local text embedding model definition for Ollama-based projects.
- Wraps `langchain_ollama.OllamaEmbeddings` with the default Ollama embedding tag.
- Produces 768-dimensional embeddings.

## Public API
- `class NomicEmbedTextModel(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.NOMIC_EMBED_TEXT`
  - `MODEL_ID`: `DEFAULT_EMBEDDING_MODEL_TAG`
  - `PROVIDER`: `ModelProvider.OLLAMA`
  - `model: EmbeddingModel`: Preconfigured embedding model instance:
    - `model_id`, `provider`, `name`, `owner`, `description`, `image`, `dimensions`
    - `model`: `OllamaEmbeddings(model=MODEL_ID, base_url=ABIModule.resolved_base_url())`
- `model: EmbeddingModel`
  - Backwards-compatible alias of `NomicEmbedTextModel.model` for direct importers.

## Configuration/Dependencies
- Depends on:
  - `langchain_ollama.OllamaEmbeddings`
  - `naas_abi_core.models.Model` (`EmbeddingModel`, `ModelDefinition`, `ModelProvider`, `CanonicalModelId`)
  - `naas_abi_marketplace.ai.ollama.ABIModule` for `base_url` resolution
  - `naas_abi_marketplace.ai.ollama.defaults.DEFAULT_EMBEDDING_MODEL_TAG` as the Ollama model tag
- Requires an accessible Ollama server at `ABIModule.resolved_base_url()`.

## Usage
```python
from naas_abi_marketplace.ai.ollama.models.nomic_embed_text import model

# LangChain OllamaEmbeddings instance:
embeddings = model.model

vec = embeddings.embed_query("Hello world")
print(len(vec))  # 768
```

## Caveats
- Input is capped at **2048 tokens**; anything beyond that is **silently dropped** by the model as served by Ollama.
- Chunk documents before embedding; long documents will be represented primarily by their beginning.
