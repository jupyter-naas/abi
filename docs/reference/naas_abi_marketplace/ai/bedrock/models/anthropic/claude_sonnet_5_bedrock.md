# ClaudeSonnet5BedrockModel

## What it is
- A Bedrock-backed model definition that registers **Anthropic Claude Sonnet 5** as a `ChatModel` using `langchain_aws.ChatBedrockConverse`.
- Exposes a ready-to-use `model` instance configured from `ABIModule` AWS/region settings.

## Public API
- `class ClaudeSonnet5BedrockModel(ModelDefinition)`
  - Purpose: declares metadata and a configured `ChatModel` for the Bedrock model `anthropic.claude-sonnet-5`.
  - Public class attributes:
    - `CANONICAL_ID`: `CanonicalModelId.CLAUDE_SONNET_5`
    - `MODEL_ID`: `"anthropic.claude-sonnet-5"`
    - `PROVIDER`: `ModelProvider.BEDROCK`
    - `model`: `ChatModel` instance wrapping `ChatBedrockConverse(...)`
- `model: ChatModel`
  - Purpose: module-level alias to `ClaudeSonnet5BedrockModel.model` for convenient importing.

## Configuration/Dependencies
- Dependencies:
  - `langchain_aws.ChatBedrockConverse`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `ModelProvider`, `CanonicalModelId`)
  - `naas_abi_marketplace.ai.bedrock.ABIModule`
- Configuration source:
  - `ABIModule.get_instance().configuration` provides:
    - `region_name`
    - `aws_access_key_id`
    - `aws_secret_access_key`
    - `aws_session_token`
- Notable model settings:
  - `context_window=1000000`
  - `ChatBedrockConverse(..., max_tokens=None)`

## Usage
```python
from naas_abi_marketplace.ai.bedrock.models.anthropic.claude_sonnet_5_bedrock import model

# The underlying LangChain chat model instance:
llm = model.model

# How you call it depends on your LangChain version; this is a common pattern:
response = llm.invoke("Hello from Claude Sonnet 5 on Bedrock.")
print(response)
```

## Caveats
- Claude Sonnet 5 rejects sampling parameters (e.g., `temperature`, `top_p`, `top_k`) with HTTP 400 per the inline comment; this implementation intentionally does **not** pass `temperature`.
