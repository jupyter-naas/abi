# Llama3370bBedrockModel

## What it is
- Defines a LangChain `ChatBedrockConverse` chat model wrapper for **Meta Llama 3.3 70B Instruct** on **AWS Bedrock**.
- Exposes a ready-to-use `ChatModel` instance (`model`) configured from the module configuration (`ABIModule`).

## Public API
- `class Llama3370bBedrockModel(ModelDefinition)`
  - Purpose: Registers model metadata and constructs the underlying Bedrock chat client.
  - Public attributes:
    - `CANONICAL_ID`: `CanonicalModelId.LLAMA_3_3_70B`
    - `MODEL_ID`: `"meta.llama3-3-70b-instruct-v1:0"`
    - `PROVIDER`: `ModelProvider.BEDROCK`
    - `model`: `ChatModel` preconfigured with:
      - `model_id`, `provider`
      - `model`: `ChatBedrockConverse(...)` with `temperature=0`, `max_tokens=None`
- `model: ChatModel`
  - Purpose: Module-level alias to `Llama3370bBedrockModel.model` for convenient import and use.

## Configuration/Dependencies
- Dependencies:
  - `langchain_aws.ChatBedrockConverse`
  - `naas_abi_core.models.Model` (`CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`)
  - `naas_abi_marketplace.ai.bedrock.ABIModule`
- Configuration source:
  - `ABIModule.get_instance().configuration` is used to supply:
    - `region_name`
    - `aws_access_key_id`
    - `aws_secret_access_key`
    - `aws_session_token`

## Usage
```python
from naas_abi_marketplace.ai.bedrock.models.llama_3_3_70b_bedrock import model

# `model.model` is the underlying LangChain chat client (ChatBedrockConverse)
response = model.model.invoke("Hello! Summarize what you can do in one sentence.")
print(response)
```

## Caveats
- Requires valid AWS Bedrock access and properly configured credentials/region via `ABIModule` configuration.
- The model is instantiated at import time using the current `ABIModule` configuration.
