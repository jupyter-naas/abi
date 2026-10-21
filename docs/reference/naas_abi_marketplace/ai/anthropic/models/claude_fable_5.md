# ClaudeFable5Model

## What it is
- A `ModelDefinition` that registers/configures Anthropic’s `claude-fable-5` as a LangChain `ChatAnthropic` chat model inside the Naas ABI marketplace.
- Exposes a prebuilt `ChatModel` instance (`model`) with metadata (context window, pricing, architecture).

## Public API
- `class ClaudeFable5Model(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.CLAUDE_FABLE_5`
  - `MODEL_ID`: `"claude-fable-5"`
  - `PROVIDER`: `ModelProvider.ANTHROPIC`
  - `model: ChatModel`: Fully configured chat model wrapper.
- `model: ChatModel`
  - Module-level alias to `ClaudeFable5Model.model` for convenient import.

## Configuration/Dependencies
- Dependencies:
  - `langchain_anthropic.ChatAnthropic`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` types (`ChatModel`, `ModelDefinition`, etc.)
  - `naas_abi_marketplace.ai.anthropic.ABIModule`
- Requires an Anthropic API key available at:
  - `ABIModule.get_instance().configuration.anthropic_api_key`
- Model configuration highlights:
  - `max_retries=2`
  - `timeout=None`, `stop=None`
  - `context_window=1_000_000`
  - Metadata includes `pricing`, `top_provider`, and `architecture`.

## Usage
```python
from naas_abi_marketplace.ai.anthropic.models.claude_fable_5 import model

# Access the underlying LangChain chat model
llm = model.model  # ChatAnthropic instance

# Example call style depends on your LangChain version.
# If available in your environment:
result = llm.invoke("Hello from Claude Fable 5")
print(result)
```

## Caveats
- Do not pass sampling parameters (e.g., `temperature`, `top_p`, `top_k`) for this model; the source notes it rejects them with HTTP 400.
