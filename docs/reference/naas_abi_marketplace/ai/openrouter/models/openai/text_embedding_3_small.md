# TextEmbedding3SmallModel

## What it is
- Defines an OpenRouter-hosted OpenAI embedding model (`openai/text-embedding-3-small`) as a `naas_abi_core` `EmbeddingModel`.
- Exposes a ready-to-use `model` instance backed by `langchain_openai.OpenAIEmbeddings`.

## Public API
- `class TextEmbedding3SmallModel(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.TEXT_EMBEDDING_3_SMALL`
  - `MODEL_ID`: `"openai/text-embedding-3-small"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: EmbeddingModel`
    - An `EmbeddingModel` configured with:
      - `model_id`: `"openai/text-embedding-3-small"`
      - `provider`: `ModelProvider.OPENROUTER`
      - `model`: `OpenAIEmbeddings(...)` (LangChain wrapper)
- `model: EmbeddingModel`
  - Module-level alias to `TextEmbedding3SmallModel.model`.

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.OpenAIEmbeddings`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`CanonicalModelId`, `EmbeddingModel`, `ModelDefinition`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- Configuration source:
  - API key is read from: `ABIModule.get_instance().configuration.openrouter_api_key`
- OpenRouter endpoint:
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.text_embedding_3_small import model

# Access the underlying LangChain embeddings client:
embeddings_client = model.model

# Example (LangChain API): embed a single query string
vector = embeddings_client.embed_query("hello world")
print(len(vector), vector[:5])
```

## Caveats
- Requires a valid OpenRouter API key available via `ABIModule` configuration (`openrouter_api_key`).
- Network access to `https://openrouter.ai/api/v1` is required.
