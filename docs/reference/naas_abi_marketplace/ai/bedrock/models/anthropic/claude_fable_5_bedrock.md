# ClaudeFable5BedrockModel

## What it is
- Defines and exposes a Bedrock-backed chat model configuration for **Anthropic Claude Fable 5** using `langchain_aws.ChatBedrockConverse`.
- Provides a ready-to-use `ChatModel` instance (`model`) with metadata (context window, pricing, architecture).

## Public API
- **Class `ClaudeFable5BedrockModel(ModelDefinition)`**
  - `CANONICAL_ID`: `CanonicalModelId.CLAUDE_FABLE_5`
  - `MODEL_ID`: `"anthropic.claude-fable-5"`
  - `PROVIDER`: `ModelProvider.BEDROCK`
  - `model: ChatModel`: Preconfigured chat model instance using `ChatBedrockConverse`.

- **Module-level `model: ChatModel`**
  - Alias to `ClaudeFable5BedrockModel.model` for convenient imports.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_aws.ChatBedrockConverse`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `ModelProvider`, `CanonicalModelId`)
  - `naas_abi_marketplace.ai.bedrock.ABIModule`

- **Runtime configuration source**
  - `ABIModule.get_instance().configuration` is used to set AWS/Bedrock connection parameters:
    - `region_name`
    - `aws_access_key_id`
    - `aws_secret_access_key`
    - `aws_session_token`

## Usage
```python
from naas_abi_marketplace.ai.bedrock.models.anthropic.claude_fable_5_bedrock import model

# Access the underlying LangChain chat model (ChatBedrockConverse)
llm = model.model

# Use llm per langchain_aws ChatBedrockConverse interface in your application
print(model.model_id)  # "anthropic.claude-fable-5"
```

## Caveats
- **Do not pass sampling parameters** (e.g., `temperature`, `top_p`, `top_k`): the code comment notes Claude Fable 5 rejects them with HTTP 400. The configured model intentionally does not set `temperature`.
- `max_tokens` is set to `None` on `ChatBedrockConverse`; token limits are described in metadata (e.g., `max_completion_tokens: 128000`) but not enforced here.
