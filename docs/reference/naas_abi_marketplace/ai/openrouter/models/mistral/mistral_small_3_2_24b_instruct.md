# MistralSmall3224bInstructModel

## What it is
- A `ModelDefinition` that registers and configures the OpenRouter-backed **Mistral Small 3.2 24B Instruct** chat model using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance via the module-level `model` variable.

## Public API
- **Class `MistralSmall3224bInstructModel(ModelDefinition)`**
  - **Constants**
    - `CANONICAL_ID`: `CanonicalModelId.MISTRAL_SMALL_3_2_24B_INSTRUCT`
    - `MODEL_ID`: `"mistralai/mistral-small-3.2-24b-instruct"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - **Attribute**
    - `model: ChatModel`: Preconfigured chat model wrapper:
      - Underlying client: `ChatOpenAI(model=..., temperature=0, timeout=120, max_retries=3, base_url="https://openrouter.ai/api/v1")`
      - Metadata: context window `128000`, name/owner/description, pricing, architecture, supported/default parameters, etc.
- **Module variable `model: ChatModel`**
  - Alias to `MistralSmall3224bInstructModel.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ModelDefinition`, `ChatModel`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Required configuration**
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set; it is used as the OpenRouter API key.
- **Endpoint**
  - Base URL: `https://openrouter.ai/api/v1`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.mistral.mistral_small_3_2_24b_instruct import model

# Access the underlying LangChain ChatOpenAI client
llm = model.model

# Example call (LangChain interface)
response = llm.invoke("Say hello in one sentence.")
print(response)
```

## Caveats
- Importing the module initializes `ChatOpenAI` immediately and reads the OpenRouter API key from `ABIModule` configuration; missing/invalid configuration will break at import time.
- The `ChatOpenAI` client is configured with `temperature=0`, even though the `ChatModel` metadata includes `default_parameters={'temperature': 0.3}`.
