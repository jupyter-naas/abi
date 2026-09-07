# TextEmbeddingAda002Model

## What it is
- A model definition that configures LangChain’s `OpenAIEmbeddings` to use OpenRouter’s `openai/text-embedding-ada-002` embedding model.
- Exposes a ready-to-use `EmbeddingModel` instance (`model`) for embedding operations.

## Public API
- `class TextEmbeddingAda002Model(ModelDefinition)`
  - Constants:
    - `CANONICAL_ID`: `CanonicalModelId.TEXT_EMBEDDING_ADA_002`
    - `MODEL_ID`: `"openai/text-embedding-ada-002"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - Attributes:
    - `model: EmbeddingModel`: Preconfigured embedding model wrapper pointing at OpenRouter.
- Module-level:
  - `model: EmbeddingModel`: Alias to `TextEmbeddingAda002Model.model`.

## Configuration/Dependencies
- Depends on:
  - `langchain_openai.OpenAIEmbeddings`
  - `naas_abi_core.models.Model` types: `CanonicalModelId`, `EmbeddingModel`, `ModelDefinition`, `ModelProvider`
  - `naas_abi_marketplace.ai.openrouter.ABIModule` for configuration access
  - `pydantic.SecretStr` for API key handling
- Uses OpenRouter base URL:
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
- Requires OpenRouter API key available at:
  - `ABIModule.get_instance().configuration.openrouter_api_key`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.text_embedding_ada_002 import model

# LangChain embeddings instance is available as model.model
embeddings = model.model

# Example (LangChain API): embed a single query string
vector = embeddings.embed_query("hello world")
print(len(vector))
```

## Caveats
- The module reads the OpenRouter API key at import time via `ABIModule.get_instance().configuration.openrouter_api_key`; missing/invalid configuration will cause failures when constructing the embeddings client.
- Uses `OpenAIEmbeddings` with a custom `base_url` pointing to OpenRouter; behavior depends on OpenRouter compatibility with the OpenAI embeddings API.
