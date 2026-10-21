# ClaudeHaiku45BedrockModel

## What it is
- Defines a Bedrock-backed `ChatModel` for Anthropic **Claude Haiku 4.5** using `langchain_aws.ChatBedrockConverse`.
- Exposes a ready-to-use module-level `model` instance.

## Public API
- **`ClaudeHaiku45BedrockModel`** (`ModelDefinition`)
  - Static metadata:
    - `CANONICAL_ID`: `CanonicalModelId.CLAUDE_HAIKU_4_5`
    - `MODEL_ID`: `"anthropic.claude-haiku-4-5"`
    - `PROVIDER`: `ModelProvider.BEDROCK`
  - **`model: ChatModel`**
    - Preconfigured chat model wrapper including:
      - `model_id`, `provider`, and underlying `ChatBedrockConverse(...)`
      - `context_window=200000`
      - `pricing={"prompt": "0.000001", "completion": "0.000005"}`
      - Additional descriptive metadata (`name`, `owner`, `description`, `architecture`, etc.)

- **`model: ChatModel`** (module-level)
  - Alias to `ClaudeHaiku45BedrockModel.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_aws.ChatBedrockConverse`
  - `naas_abi_core.models.Model` types (`ChatModel`, `ModelDefinition`, etc.)
  - `naas_abi_marketplace.ai.bedrock.ABIModule`

- **Configuration source**
  - Pulled from: `ABIModule.get_instance().configuration`
  - Used fields:
    - `region_name`
    - `aws_access_key_id`
    - `aws_secret_access_key`
    - `aws_session_token`

- **Model runtime settings**
  - `temperature=0`
  - `max_tokens=None`

## Usage
```python
from naas_abi_marketplace.ai.bedrock.models.anthropic.claude_haiku_4_5_bedrock import model

# `model.model` is the underlying ChatBedrockConverse instance
llm = model.model
# Use `llm` according to langchain_aws.ChatBedrockConverse API in your project.
print(model.model_id, model.provider)
```

## Caveats
- Requires valid AWS Bedrock credentials and region via `ABIModule` configuration.
- This module only defines/wires the model; it does not provide higher-level chat invocation helpers beyond the underlying `ChatBedrockConverse`.
