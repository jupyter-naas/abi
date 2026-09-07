# O3DeepResearchModel

## What it is
- Defines an OpenRouter-backed LangChain chat model configuration for **OpenAI `openai/o3-deep-research`**.
- Exposes a ready-to-use `ChatModel` instance configured with `ChatOpenAI`.

## Public API
- `class O3DeepResearchModel(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.O3_DEEP_RESEARCH`
  - `MODEL_ID`: `"openai/o3-deep-research"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`: Preconfigured chat model (LangChain `ChatOpenAI`) with:
    - `temperature=0`, `timeout=120`, `max_retries=3`
    - `base_url="https://openrouter.ai/api/v1"`
    - `api_key` sourced from `ABIModule.get_instance().configuration.openrouter_api_key`
    - Metadata including `context_window=200000`, pricing, supported parameters, etc.
- `model: ChatModel`
  - Module-level alias to `O3DeepResearchModel.model`.

## Configuration/Dependencies
- Requires:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model` types (`ChatModel`, `ModelDefinition`, etc.)
  - `naas_abi_marketplace.ai.openrouter.ABIModule` for OpenRouter API key lookup
  - `pydantic.SecretStr`
- Configuration source:
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set.

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.o3_deep_research import model

# Access the underlying LangChain chat model
llm = model.model  # ChatOpenAI instance

# Example invocation (LangChain-style)
result = llm.invoke("Summarize the latest research on retrieval-augmented generation.")
print(result)
```

## Caveats
- The model description notes: it **always uses the `web_search` tool**, which **adds additional cost**.
