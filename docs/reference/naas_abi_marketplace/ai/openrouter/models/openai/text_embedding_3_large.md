# TextEmbedding3LargeModel

## What it is
- Defines an OpenRouter-backed embedding model configuration for **`openai/text-embedding-3-large`** using `langchain_openai.OpenAIEmbeddings`.
- Exposes a ready-to-use `EmbeddingModel` instance as a module-level variable.

## Public API
- `class TextEmbedding3LargeModel(ModelDefinition)`
  - Purpose: Declares canonical metadata and constructs an `EmbeddingModel` wired to OpenRouter.
  - Public attributes:
    - `CANONICAL_ID`: `CanonicalModelId.TEXT_EMBEDDING_3_LARGE`
    - `MODEL_ID`: `"openai/text-embedding-3-large"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
    - `model`: `EmbeddingModel` configured with `OpenAIEmbeddings`
- `model: EmbeddingModel`
  - Purpose: Convenience alias to `TextEmbedding3LargeModel.model`.

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.OpenAIEmbeddings`
  - `naas_abi_core.models.Model`: `CanonicalModelId`, `EmbeddingModel`, `ModelDefinition`, `ModelProvider`
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
  - `pydantic.SecretStr`
- Configuration:
  - Reads API key from `ABIModule.get_instance().configuration.openrouter_api_key`
- Endpoint:
  - Uses OpenRouter base URL: `https://openrouter.ai/api/v1`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.text_embedding_3_large import model

# Underlying embeddings client (LangChain OpenAIEmbeddings)
embeddings = model.model

vector = embeddings.embed_query("hello world")
print(len(vector))
```

## Caveats
- `ABIModule` must be initialized/configured so `openrouter_api_key` is available.
- Calls are routed through OpenRouter (`base_url="https://openrouter.ai/api/v1"`).
