# AirgapChatOpenAI (Gemma3 Airgap Model)

## What it is
- A minimal `langchain_openai.ChatOpenAI` subclass that adapts prompts and streaming to a local **Docker Model Runner** endpoint (OpenAI-compatible `/chat/completions`).
- The module also exports a preconfigured `ChatModel` instance for **Gemma3** running in “airgap” (local) mode.

## Public API
- **class `AirgapChatOpenAI(ChatOpenAI)`**
  - Purpose: Provide basic prompt formatting and robust streaming against a local OpenAI-compatible server.
  - Public methods/properties:
    - `bind_tools(tools, **kwargs) -> self`: No-op tool binding; returns `self`.
    - `bind(**kwargs) -> self`: No-op binding; returns `self`.
    - `_llm_type -> str`: Returns `"airgap_chat_openai"`.
- **Module-level constants**
  - `MODEL_ID = "ai/gemma3"`
  - `NAME = "gemma3-airgap"`
  - `DESCRIPTION`, `IMAGE`, `CONTEXT_WINDOW = 8192`, `PROVIDER = "google"`
- **`model: ChatModel`**
  - Purpose: Ready-to-use `naas_abi_core.models.Model.ChatModel` wrapper configured with `AirgapChatOpenAI` pointing to `http://localhost:12434/engines/v1`.

## Configuration/Dependencies
- **HTTP endpoint**
  - Expects an OpenAI-compatible server at:
    - `openai_api_base="http://localhost:12434/engines/v1"`
  - Streaming uses `POST {openai_api_base}/chat/completions` with `stream=True`.
- **Python dependencies**
  - `requests`
  - `langchain_core`, `langchain_openai`
  - `naas_abi_core` (for `logger` and `ChatModel`)

## Usage
```python
from naas_abi.models.airgap_gemma import model

# Access the underlying LangChain chat model
llm = model.model

# Minimal invoke example (LangChain interface)
response = llm.invoke("Say hello in one sentence.")
print(response.content)
```

## Caveats
- Only the **last** `HumanMessage` content is used; system messages (detected by `"SystemMessage"` in type name) are concatenated into a single “System:” block.
- If no user message is provided (or it’s empty), it defaults to `"Hello"`.
- `bind_tools()` does not actually store or apply tools; `_generate()` forces `tool_calls = []` on the returned `AIMessage` to avoid routing issues.
- Streaming error handling returns chunks containing user-visible error text on:
  - timeout (`finish_reason="timeout"`)
  - connection error (`"connection_error"`)
  - generic error (`"error"`)
