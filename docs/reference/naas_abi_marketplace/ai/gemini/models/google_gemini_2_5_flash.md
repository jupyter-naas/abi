# google_gemini_2_5_flash

## What it is
Registers a preconfigured `ChatModel` for Google Gemini **`gemini-2.5-flash`**, backed by LangChain’s `ChatGoogleGenerativeAI` and initialized with the Gemini API key from `ABIModule` configuration.

## Public API
- **Constants**
  - `MODEL_ID`: `"gemini-2.5-flash"` — Gemini model identifier.
  - `PROVIDER`: `"google"` — provider identifier.
- **Objects**
  - `model: ChatModel` — initialized chat model wrapper:
    - `model_id`: `MODEL_ID`
    - `provider`: `PROVIDER`
    - `model`: `ChatGoogleGenerativeAI(model=MODEL_ID, api_key=SecretStr(...))`

## Configuration/Dependencies
- **Dependencies**
  - `langchain_google_genai.ChatGoogleGenerativeAI`
  - `naas_abi_core.models.Model.ChatModel`
  - `naas_abi_marketplace.ai.gemini.ABIModule`
  - `pydantic.SecretStr`
- **Configuration**
  - API key is read from `ABIModule.get_instance().configuration.gemini_api_key`
  - Key is wrapped in `SecretStr` and passed to `ChatGoogleGenerativeAI`.

## Usage
```python
from naas_abi_marketplace.ai.gemini.models.google_gemini_2_5_flash import model

llm = model.model  # ChatGoogleGenerativeAI instance
print(model.model_id, model.provider)
```

## Caveats
- Import-time initialization depends on `ABIModule` being configured with `gemini_api_key`; missing/invalid configuration may cause import failures.
