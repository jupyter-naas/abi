# NovaProBedrockModel

## What it is
- A Bedrock-backed chat model definition for **Amazon Nova Pro** (`amazon.nova-pro-v1:0`) using `langchain_aws.ChatBedrockConverse`.
- Exposes a ready-to-use `ChatModel` instance configured from the marketplace Bedrock `ABIModule` configuration.

## Public API
- `class NovaProBedrockModel(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.NOVA_PRO`
  - `MODEL_ID`: `"amazon.nova-pro-v1:0"`
  - `PROVIDER`: `ModelProvider.BEDROCK`
  - `model: ChatModel`: Preconfigured chat model instance
- `model: ChatModel`
  - Module-level alias to `NovaProBedrockModel.model` for convenient imports

## Configuration/Dependencies
- Dependencies:
  - `langchain_aws.ChatBedrockConverse`
  - `naas_abi_core.models.Model` (`CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`)
  - `naas_abi_marketplace.ai.bedrock.ABIModule`
- Configuration source:
  - `ABIModule.get_instance().configuration` providing:
    - `region_name`
    - `aws_access_key_id`
    - `aws_secret_access_key`
    - `aws_session_token`
- Fixed model parameters (in this file):
  - `temperature=0`
  - `max_tokens=None`

## Usage
```python
from naas_abi_marketplace.ai.bedrock.models.nova_pro_bedrock import model

# `model` is a ChatModel wrapper; the underlying LangChain model is available at `model.model`.
llm = model.model

# Example invocation shape depends on LangChain version and message classes in use.
# Common pattern:
result = llm.invoke("Hello from Nova Pro")
print(result)
```

## Caveats
- Requires valid AWS Bedrock credentials and region provided via `ABIModule` configuration.
- The exact return type and message formatting for `.invoke()` depends on the installed `langchain_aws` / LangChain versions.
