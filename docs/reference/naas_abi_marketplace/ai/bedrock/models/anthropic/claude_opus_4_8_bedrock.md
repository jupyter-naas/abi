# ClaudeOpus48BedrockModel

## What it is
- A Bedrock-backed `ModelDefinition` that registers Anthropic **Claude Opus 4.8** as a `ChatModel`.
- Uses `langchain_aws.ChatBedrockConverse` configured from `ABIModule` AWS settings.

## Public API
- `class ClaudeOpus48BedrockModel(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.CLAUDE_OPUS_4_8`
  - `MODEL_ID`: `"anthropic.claude-opus-4-8"`
  - `PROVIDER`: `ModelProvider.BEDROCK`
  - `model: ChatModel`
    - Preconfigured `ChatModel` instance, including:
      - Bedrock Converse client (`ChatBedrockConverse`) with AWS credentials and region.
      - Metadata such as `context_window=1000000`, pricing, and architecture fields.
- `model: ChatModel`
  - Module-level alias to `ClaudeOpus48BedrockModel.model`.

## Configuration/Dependencies
- Depends on:
  - `langchain_aws.ChatBedrockConverse`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `ModelProvider`, `CanonicalModelId`)
  - `naas_abi_marketplace.ai.bedrock.ABIModule` for configuration
- Configuration source:
  - `ABIModule.get_instance().configuration`, providing:
    - `region_name`
    - `aws_access_key_id`
    - `aws_secret_access_key`
    - `aws_session_token`

## Usage
```python
from naas_abi_marketplace.ai.bedrock.models.anthropic.claude_opus_4_8_bedrock import model

# 'model' is a naas_abi_core ChatModel wrapper.
# Access the underlying LangChain chat client via `model.model`.
llm = model.model

# Example invocation (LangChain style; message schema depends on your stack)
# result = llm.invoke("Write a short function to validate an email address.")
# print(result)
```

## Caveats
- Claude Opus 4.8 rejects sampling parameters (`temperature`, `top_p`, `top_k`) with HTTP 400; this definition does not pass `temperature`.
- `max_tokens` is set to `None` in `ChatBedrockConverse` (token limits are not enforced here).
