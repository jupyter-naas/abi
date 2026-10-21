# ClaudeSonnet4BedrockModel

## What it is
- A Bedrock-backed **Anthropic Claude Sonnet 4** chat model definition.
- Exposes a preconfigured `ChatModel` instance using `langchain_aws.ChatBedrockConverse` and credentials/region from `ABIModule` configuration.

## Public API
- `class ClaudeSonnet4BedrockModel(ModelDefinition)`
  - Defines the model metadata and a ready-to-use `model: ChatModel`.
  - Class attributes:
    - `CANONICAL_ID`: `CanonicalModelId.CLAUDE_SONNET_4`
    - `MODEL_ID`: `"anthropic.claude-sonnet-4-20250514-v1:0"`
    - `PROVIDER`: `ModelProvider.BEDROCK`
  - `model: ChatModel`
    - `model_id`: the Bedrock model id above
    - `provider`: `ModelProvider.BEDROCK`
    - `model`: a `ChatBedrockConverse` instance configured with:
      - `region_name`, `aws_access_key_id`, `aws_secret_access_key`, `aws_session_token` from `ABIModule.get_instance().configuration`
      - `temperature=0`
      - `max_tokens=None`
- Module-level export:
  - `model: ChatModel` — alias to `ClaudeSonnet4BedrockModel.model`

## Configuration/Dependencies
- Dependencies:
  - `langchain_aws.ChatBedrockConverse`
  - `naas_abi_core.models.Model` (`CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`)
  - `naas_abi_marketplace.ai.bedrock.ABIModule`
- Configuration source:
  - `ABIModule.get_instance().configuration` must provide:
    - `region_name`
    - `aws_access_key_id`
    - `aws_secret_access_key`
    - `aws_session_token` (can be `None` depending on your setup)

## Usage
```python
from naas_abi_marketplace.ai.bedrock.models.anthropic.claude_sonnet_4_bedrock import model

# `model.model` is a ChatBedrockConverse instance (LangChain chat model).
llm = model.model

# Example invocation style depends on your LangChain version.
# Common pattern:
response = llm.invoke("Hello from Bedrock Claude Sonnet 4")
print(response)
```

## Caveats
- Requires valid AWS Bedrock access and correct region/credentials available via `ABIModule` configuration.
- The model is configured with `temperature=0` and `max_tokens=None` (provider/model defaults will apply for token limits).
