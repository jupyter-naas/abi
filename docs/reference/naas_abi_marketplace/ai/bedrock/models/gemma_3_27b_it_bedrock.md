# `Gemma327bItBedrockModel`

## What it is
- A Bedrock-backed LangChain chat model definition for **Google Gemma 3 27B IT**.
- Exposes a preconfigured `ChatModel` instance using `langchain_aws.ChatBedrockConverse` and ABI Marketplace configuration.

## Public API
- **Class `Gemma327bItBedrockModel` (`ModelDefinition`)**
  - `CANONICAL_ID`: `CanonicalModelId.GEMMA_3_27B_IT`
  - `MODEL_ID`: `"google.gemma-3-27b-it"`
  - `PROVIDER`: `ModelProvider.BEDROCK`
  - `model: ChatModel`: A configured chat model wrapper.
- **Module-level `model: ChatModel`**
  - Alias to `Gemma327bItBedrockModel.model` for convenient import/use.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_aws.ChatBedrockConverse`
  - `naas_abi_core.models.Model` (`CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`)
  - `naas_abi_marketplace.ai.bedrock.ABIModule`
- **Configuration source**
  - Uses `ABIModule.get_instance().configuration` to provide:
    - `region_name`
    - `aws_access_key_id`
    - `aws_secret_access_key`
    - `aws_session_token`
- **Model settings (hardcoded)**
  - `temperature=0`
  - `max_tokens=None`

## Usage
```python
from naas_abi_marketplace.ai.bedrock.models.gemma_3_27b_it_bedrock import model

# `model` is a ChatModel wrapper around a ChatBedrockConverse instance.
# Use it according to the ChatModel interface in naas_abi_core.
print(model.model_id)  # "google.gemma-3-27b-it"
print(model.provider)  # ModelProvider.BEDROCK
```

## Caveats
- Requires valid AWS/Bedrock configuration available via `ABIModule` (region and credentials/session token).
- The underlying client is created at import time using the current `ABIModule` configuration.
