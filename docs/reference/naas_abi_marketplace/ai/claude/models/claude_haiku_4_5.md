# claude_haiku_4_5

## What it is
- A module-level `ChatModel` instance configured to use Anthropic’s Claude model `claude-haiku-4-5-20251001` via `langchain_anthropic.ChatAnthropic`.

## Public API
- `MODEL_ID: str`
  - The Anthropic model name: `"claude-haiku-4-5-20251001"`.
- `PROVIDER: str`
  - The provider identifier: `"anthropic"`.
- `model: naas_abi_core.models.Model.ChatModel`
  - Preconfigured chat model wrapper containing a `ChatAnthropic` client with:
    - `temperature=0`
    - `max_retries=2`
    - `timeout=None`
    - `stop=None`
    - `api_key` pulled from `ABIModule.get_instance().configuration.anthropic_api_key`

## Configuration/Dependencies
- **Dependencies**
  - `langchain_anthropic.ChatAnthropic`
  - `naas_abi_marketplace.ai.claude.ABIModule`
  - `naas_abi_core.models.Model.ChatModel`
  - `pydantic.SecretStr`
- **Configuration**
  - Requires `ABIModule.get_instance().configuration.anthropic_api_key` to be set (used to initialize `ChatAnthropic`).

## Usage
```python
from naas_abi_marketplace.ai.claude.models.claude_haiku_4_5 import model

# Use the underlying LangChain model client
llm = model.model  # ChatAnthropic instance
```

## Caveats
- This module only defines and exports a preconfigured `ChatModel`; actual invocation patterns depend on how `ChatModel` and `ChatAnthropic` are used elsewhere in your codebase.
- If `anthropic_api_key` is missing/invalid in `ABIModule` configuration, initialization or requests will fail.
