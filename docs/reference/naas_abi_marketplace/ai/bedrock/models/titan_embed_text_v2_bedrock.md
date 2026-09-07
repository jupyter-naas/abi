# TitanEmbedTextV2BedrockModel

## What it is
- A `ModelDefinition` that registers an Amazon Bedrock embedding model (`amazon.titan-embed-text-v2:0`) using `langchain_aws.BedrockEmbeddings`.
- Exposes both:
  - a wrapped `EmbeddingModel` (`model`)
  - and a raw `BedrockEmbeddings` instance (`embedding_model`) for backward compatibility.

## Public API
- **Class: `TitanEmbedTextV2BedrockModel`**
  - `CANONICAL_ID`: `CanonicalModelId.TITAN_EMBED_TEXT_V2`
  - `MODEL_ID`: `"amazon.titan-embed-text-v2:0"`
  - `PROVIDER`: `ModelProvider.BEDROCK`
  - `model: EmbeddingModel`: wrapper containing metadata and the underlying `BedrockEmbeddings` client

- **Module-level symbols**
  - `model: EmbeddingModel`: alias to `TitanEmbedTextV2BedrockModel.model`
  - `embedding_model: BedrockEmbeddings`: alias to `model.model` (raw LangChain Bedrock embeddings client)

## Configuration/Dependencies
- **Dependencies**
  - `langchain_aws.BedrockEmbeddings`
  - `naas_abi_core.models.Model` (`CanonicalModelId`, `EmbeddingModel`, `ModelDefinition`, `ModelProvider`)
  - `naas_abi_marketplace.ai.bedrock.ABIModule`

- **Configuration source**
  - AWS/Bedrock settings are read from: `ABIModule.get_instance().configuration`
  - Used fields:
    - `region_name`
    - `aws_access_key_id`
    - `aws_secret_access_key`
    - `aws_session_token`

## Usage
```python
from naas_abi_marketplace.ai.bedrock.models.titan_embed_text_v2_bedrock import (
    model,
    embedding_model,
)

# Wrapped EmbeddingModel (contains metadata + underlying client)
client = model.model  # BedrockEmbeddings

# Back-compat: directly use the raw BedrockEmbeddings instance
client2 = embedding_model
```

## Caveats
- Instantiation depends on `ABIModule.get_instance().configuration` being available and populated with valid AWS credentials/region.
