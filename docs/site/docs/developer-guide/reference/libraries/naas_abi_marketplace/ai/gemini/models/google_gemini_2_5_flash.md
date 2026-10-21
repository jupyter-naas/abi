# google_gemini_2_5_flash

## What it is
A module-level `ChatModel` registration for Google’s Gemini model **`gemini-2.5-flash`**, wired to LangChain’s `ChatGoogleGenerativeAI` using the configured Gemini API key.

## Public API
- **Constants**
  - `MODEL_ID`: `"gemini-2.5-flash"` — the Gemini model name.
  - `PROVIDER`: `"google"` — provider identifier.
- **Objects**
  - `model: ChatModel` — a preconfigured chat model instance:
    - `model_id`: `MODEL_ID`
    - `provider`: `PROVIDER`
    - `model`: `ChatGoogleGenerativeAI(model=MODEL_ID, api_key=SecretStr(...))`

## Configuration/Dependencies
- **Dependencies**
  - `langchain_google_genai.ChatGoogleGenerativeAI`
  - `naas_abi_core.models.Model.ChatModel`
  - `naas_abi_marketplace.ai.gemini.ABIModule`
  - `pydantic.SecretStr`
- **Configuration source**
  - API key is read from: `ABIModule.get_instance().configuration.gemini_api_key`
  - Wrapped with `SecretStr` before being passed to `ChatGoogleGenerativeAI`.

## Usage
```python
from naas_abi_marketplace.ai.gemini.models.google_gemini_2_5_flash import model

# `model` is a ChatModel wrapper holding a LangChain ChatGoogleGenerativeAI instance.
llm = model.model  # underlying ChatGoogleGenerativeAI
print(model.model_id, model.provider)
```

## Caveats
- Requires `ABIModule` to be properly configured with `gemini_api_key`; otherwise model initialization may fail at import time.
