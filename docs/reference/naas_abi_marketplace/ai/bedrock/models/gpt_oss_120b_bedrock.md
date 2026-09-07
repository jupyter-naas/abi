# GptOss120bBedrockModel

## What it is
- Defines a Bedrock-backed chat model configuration for the canonical model **`GPT_OSS_120B`**.
- Exposes a ready-to-use `ChatModel` instance wired to `langchain_aws.ChatBedrockConverse`.

## Public API
- **`class GptOss120bBedrockModel(ModelDefinition)`**
  - **`CANONICAL_ID`**: `CanonicalModelId.GPT_OSS_120B`
  - **`MODEL_ID`**: `"openai.gpt-oss-120b-1:0"`
  - **`PROVIDER`**: `ModelProvider.BEDROCK`
  - **`model: ChatModel`**: Preconfigured `ChatModel` that wraps a `ChatBedrockConverse` client.
- **`model: ChatModel`** (module-level)
  - Alias to `GptOss120bBedrockModel.model` for convenient import/use.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_aws.ChatBedrockConverse`
  - `naas_abi_core.models.Model` (`CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`)
  - `naas_abi_marketplace.ai.bedrock.ABIModule`
- **Configuration source**
  - Uses `ABIModule.get_instance().configuration` for AWS/Bedrock settings:
    - `region_name`
    - `aws_access_key_id`
    - `aws_secret_access_key`
    - `aws_session_token`
- **Model client parameters**
  - `temperature=0`
  - `max_tokens=None`

## Usage
```python
from naas_abi_marketplace.ai.bedrock.models.gpt_oss_120b_bedrock import model

# `model` is a ChatModel wrapper; access its underlying LangChain chat client:
llm = model.model

# Use `llm` with LangChain patterns appropriate for ChatBedrockConverse in your stack.
print(llm)
```

## Caveats
- Instantiation reads configuration at import time via `ABIModule.get_instance().configuration`; missing/invalid AWS config will surface when the module is imported or when the client is used.
- No explicit `max_tokens` limit is set (`None`), leaving token limits to service defaults/constraints.
