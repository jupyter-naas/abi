# TextEmbedding3LargeModel

## What it is
- A model definition that wires OpenAI’s `text-embedding-3-large` embedding model into the Naas ABI model registry using `langchain_openai.OpenAIEmbeddings`.
- Exposes an `EmbeddingModel` instance for use by other components.

## Public API
- `class TextEmbedding3LargeModel(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.TEXT_EMBEDDING_3_LARGE`
  - `MODEL_ID`: `"text-embedding-3-large"`
  - `PROVIDER`: `ModelProvider.OPENAI`
  - `model: EmbeddingModel`
    - Preconfigured `EmbeddingModel` that wraps `OpenAIEmbeddings(model="text-embedding-3-large", api_key=...)`.

- `model: EmbeddingModel`
  - Module-level alias for `TextEmbedding3LargeModel.model` (backward-compatible for direct importers).

## Configuration/Dependencies
- Depends on:
  - `langchain_openai.OpenAIEmbeddings`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` types (`ModelDefinition`, `EmbeddingModel`, etc.)
  - `naas_abi_marketplace.ai.chatgpt.ABIModule` for configuration access
- Requires an OpenAI API key available at:
  - `ABIModule.get_instance().configuration.openai_api_key`

## Usage
```python
from naas_abi_marketplace.ai.chatgpt.models.text_embedding_3_large import model

# model is an EmbeddingModel wrapper; the underlying LangChain embeddings are in model.model
embeddings = model.model.embed_query("hello world")
print(len(embeddings), embeddings[:5])
```

## Caveats
- Import-time initialization reads `ABIModule.get_instance().configuration.openai_api_key`; missing/invalid configuration can cause import or runtime failures.
- The `api_key` is wrapped as `SecretStr`, but it still must be present and valid for API calls.
