# ClaudeHaiku35BedrockModel

## What it is
- A Bedrock-backed LangChain chat model definition for Anthropic **Claude 3.5 Haiku**.
- Exposes a ready-to-use `ChatModel` instance configured from the module’s Bedrock/AWS configuration.

## Public API
- **Class `ClaudeHaiku35BedrockModel`** (`ModelDefinition`)
  - **Constants**
    - `CANONICAL_ID`: `CanonicalModelId.CLAUDE_HAIKU_3_5`
    - `MODEL_ID`: `"anthropic.claude-3-5-haiku-20241022-v1:0"`
    - `PROVIDER`: `ModelProvider.BEDROCK`
  - **Attribute**
    - `model: ChatModel` — a configured chat model wrapping `langchain_aws.ChatBedrockConverse`.
- **Module-level**
  - `model: ChatModel` — alias to `ClaudeHaiku35BedrockModel.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_aws.ChatBedrockConverse`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `ModelProvider`, `CanonicalModelId`)
  - `naas_abi_marketplace.ai.bedrock.ABIModule`
- **Configuration source**
  - `ABIModule.get_instance().configuration`, used for:
    - `region_name`
    - `aws_access_key_id`
    - `aws_secret_access_key`
    - `aws_session_token`
- **Model runtime parameters**
  - `temperature=0`
  - `max_tokens=None`

## Usage
```python
from naas_abi_marketplace.ai.bedrock.models.anthropic.claude_haiku_3_5_bedrock import model

# `model` is a ChatModel wrapper; access the underlying LangChain model if needed:
llm = model.model  # ChatBedrockConverse instance

resp = llm.invoke("Say hello in one sentence.")
print(resp)
```

## Caveats
- Requires valid AWS/Bedrock configuration available via `ABIModule.get_instance().configuration`.
- This module fixes `temperature` to `0` and does not set a `max_tokens` limit (`None`).
