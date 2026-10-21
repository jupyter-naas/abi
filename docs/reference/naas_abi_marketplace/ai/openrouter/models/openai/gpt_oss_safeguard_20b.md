# GptOssSafeguard20bModel

## What it is
- A model definition that configures an OpenRouter-hosted OpenAI chat model (`openai/gpt-oss-safeguard-20b`) via `langchain_openai.ChatOpenAI`.
- Exposes a prebuilt `ChatModel` instance (`model`) for use elsewhere in the package.

## Public API
- `class GptOssSafeguard20bModel(ModelDefinition)`
  - Purpose: registers metadata and a configured `ChatModel` for `openai/gpt-oss-safeguard-20b`.
  - Public attributes:
    - `CANONICAL_ID`: `CanonicalModelId.GPT_OSS_SAFEGUARD_20B`
    - `MODEL_ID`: `"openai/gpt-oss-safeguard-20b"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
    - `model: ChatModel`: configured chat model wrapper (includes underlying `ChatOpenAI`).
- Module-level:
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
  - `model: ChatModel`: alias of `GptOssSafeguard20bModel.model`

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- Requires configuration:
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set; it is passed as `api_key` to `ChatOpenAI`.
- `ChatOpenAI` is configured with:
  - `model="openai/gpt-oss-safeguard-20b"`
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`
  - `base_url="https://openrouter.ai/api/v1"`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_oss_safeguard_20b import model

# Access the underlying LangChain ChatOpenAI instance
llm = model.model

# Example invocation (requires ABIModule OpenRouter API key to be configured)
result = llm.invoke("Classify this text for safety: ...")
print(result)
```

## Caveats
- Importing this module constructs the `ChatOpenAI` instance immediately and reads `ABIModule` configuration at import time. If the OpenRouter API key is not available then, imports may fail.
