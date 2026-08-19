# ClaudeSonnet5Model

## What it is
- A `ModelDefinition` that registers/configures Anthropic’s **Claude Sonnet 5** as a `ChatModel` using `langchain_anthropic.ChatAnthropic`.
- Exposes a ready-to-use `model` object at module level.

## Public API
- `class ClaudeSonnet5Model(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.CLAUDE_SONNET_5`
  - `MODEL_ID`: `"claude-sonnet-5"`
  - `PROVIDER`: `ModelProvider.ANTHROPIC`
  - `model: ChatModel`: Fully configured chat model wrapper, including metadata (context window, pricing, architecture, etc.).
- `model: ChatModel`
  - Alias to `ClaudeSonnet5Model.model` for convenient imports.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_anthropic.ChatAnthropic`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `ModelProvider`, `CanonicalModelId`)
  - `naas_abi_marketplace.ai.anthropic.ABIModule`
- **Configuration source**
  - API key is loaded from: `ABIModule.get_instance().configuration.anthropic_api_key`
- **Key runtime settings (ChatAnthropic)**
  - `model_name="claude-sonnet-5"`
  - `max_retries=2`
  - `max_tokens_to_sample=8192` (explicitly set)
  - `timeout=None`
  - `stop=None`

## Usage
```python
from naas_abi_marketplace.ai.anthropic.models.claude_sonnet_5 import model

# `model` is a naas_abi_core ChatModel wrapper; the underlying LangChain model is on `model.model`.
llm = model.model

result = llm.invoke("Write a one-sentence summary of Claude Sonnet 5.")
print(result)
```

## Caveats
- Requires `ABIModule` to be initialized/configured with a valid `anthropic_api_key`; otherwise construction/use will fail.
- The module sets `max_tokens_to_sample=8192` for the LangChain client; this constrains sampled completion length for requests made through this configured instance.
