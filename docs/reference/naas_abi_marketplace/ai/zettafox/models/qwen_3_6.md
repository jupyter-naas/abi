# Qwen36Model

## What it is
- A `ModelDefinition` that registers/configures the **Qwen 3.6 35B A3B FP8** chat model for use via **Zettafox’s LiteLLM OpenAI-compatible endpoint** using LangChain’s `ChatOpenAI`.

## Public API
- `class Qwen36Model(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.QWEN_3_6`
  - `MODEL_ID`: `"Qwen/Qwen3.6-35B-A3B-FP8"`
  - `PROVIDER`: `ModelProvider.QWEN`
  - `model: ChatModel`
    - `model_id`, `provider`, `name`, `description`, `context_window`
    - wraps a configured `ChatOpenAI` client:
      - `base_url="https://llm.zettafox.com/litellm"`
      - `default_headers={"Authorization": _cfg.qwen_litellm_auth_header}`
      - `temperature=0`, `top_p=0.1`, `timeout=120`, `max_retries=3`
      - `model_kwargs={"max_tokens": 100000}`
      - `extra_body={"repetition_penalty": 1.1}`
- `model: ChatModel`
  - Back-compat alias for `Qwen36Model.model` (for `from ... import model` import style).

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ModelDefinition`, `ChatModel`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.zettafox.ABIModule`
- Configuration source:
  - `ABIModule.get_instance().configuration.qwen_litellm_auth_header`
    - Used as the `Authorization` header for the LiteLLM endpoint.
- Notes:
  - `api_key` is set to `SecretStr("unused")`; authentication is done via `default_headers`.

## Usage
```python
from naas_abi_marketplace.ai.zettafox.models.qwen_3_6 import model

# Access the underlying LangChain ChatOpenAI client
llm = model.model

# Example call (method name depends on your LangChain version)
resp = llm.invoke("Say hello in one sentence.")
print(resp)
```

## Caveats
- Requires `ABIModule` configuration to provide `qwen_litellm_auth_header`; without it, requests will not be authorized.
- Large token settings are configured (`context_window=500000`, `max_tokens=100000`); ensure your backend supports these limits.
