# `Gemini25ProBedrockModel`

## What it is
- A Bedrock-backed LangChain chat model definition for **Google Gemini 2.5 Pro** exposed via **AWS Bedrock**.
- Exposes a ready-to-use `ChatModel` instance configured from `ABIModule` AWS credentials/region.

## Public API
- `class Gemini25ProBedrockModel(ModelDefinition)`
  - Purpose: Defines a canonical model mapping and constructs the underlying Bedrock chat client.
  - Public attributes:
    - `CANONICAL_ID`: `CanonicalModelId.GEMINI_2_5_PRO`
    - `MODEL_ID`: `"us.google.gemini-2-5-pro-v1:0"`
    - `PROVIDER`: `ModelProvider.BEDROCK`
    - `model`: `ChatModel` wrapping a `langchain_aws.ChatBedrockConverse` instance
- `model: ChatModel`
  - Purpose: Module-level alias to `Gemini25ProBedrockModel.model` for convenient import/use.

## Configuration/Dependencies
- Dependencies:
  - `langchain_aws.ChatBedrockConverse`
  - `naas_abi_core.models.Model` (`CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`)
  - `naas_abi_marketplace.ai.bedrock.ABIModule`
- Configuration source:
  - `ABIModule.get_instance().configuration` is used to populate:
    - `region_name`
    - `aws_access_key_id`
    - `aws_secret_access_key`
    - `aws_session_token`
- Fixed runtime parameters (as defined in code):
  - `temperature=0`
  - `max_tokens=None`

## Usage
```python
from naas_abi_marketplace.ai.bedrock.models.gemini_2_5_pro_bedrock import model

# `model.model` is the underlying LangChain ChatBedrockConverse instance.
llm = model.model

# Example call shape depends on your LangChain version/integration.
# For many LangChain chat models, this works:
response = llm.invoke("Hello from Gemini 2.5 Pro on Bedrock")
print(response)
```

## Caveats
- Requires valid AWS Bedrock access and correct `ABIModule` configuration (region and credentials).
- The module constructs the client at import time using `ABIModule.get_instance().configuration`.
