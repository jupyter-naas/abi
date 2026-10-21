# AirgapChatOpenAI (Gemma3 Airgap Model)

## What it is
- A minimal wrapper around `langchain_openai.ChatOpenAI` that targets a local **Docker Model Runner** endpoint for Gemma3 (`ai/gemma3`).
- Provides:
  - Prompt formatting (System/User/Assistant style) before sending requests.
  - Basic streaming via direct HTTP requests to the runner.
  - Simplified tool-call handling (forces empty `tool_calls` to avoid routing issues).

## Public API
### Class: `AirgapChatOpenAI(ChatOpenAI)`
- `__init__(**kwargs)`
  - Initializes the underlying `ChatOpenAI` and a private `_tools` list (unused).
- `bind_tools(tools, **kwargs) -> AirgapChatOpenAI`
  - No-op: returns `self` without storing tools.
- `bind(**kwargs) -> AirgapChatOpenAI`
  - No-op: returns `self`.
- Property: `_llm_type -> str`
  - Returns `"airgap_chat_openai"`.
- `_generate(messages, stop=None, run_manager=None, **kwargs) -> ChatResult`
  - Extracts any system prompt and last human message, builds a single user prompt:
    - `System: ...`
    - `User: ...`
    - `Assistant:`
  - Calls parent `_generate` with filtered kwargs (`temperature`, `max_tokens`, `stop`).
  - Forces the returned first generation message to an `AIMessage` with `tool_calls = []`.
- `_stream(messages, stop=None, run_manager=None, **kwargs) -> Iterator[ChatGenerationChunk]`
  - Sends a streaming POST request to `"{openai_api_base}/chat/completions"` using `requests`.
  - Parses `data: {json}` lines and yields `ChatGenerationChunk` with `AIMessageChunk(content=...)`.
  - On timeout/connection/error, yields a final chunk containing an error message.

### Module-level model registration
Constants:
- `MODEL_ID = "ai/gemma3"`
- `NAME = "gemma3-airgap"`
- `DESCRIPTION`, `IMAGE`, `CONTEXT_WINDOW = 8192`, `PROVIDER = "google"`

Object:
- `model: ChatModel`
  - `model.model` is an `AirgapChatOpenAI` configured with:
    - `model="ai/gemma3"`
    - `temperature=0.2`
    - `max_tokens=512`
    - `openai_api_base="http://localhost:12434/engines/v1"`
    - `api_key="ignored"`

## Configuration/Dependencies
- Python deps:
  - `langchain_openai`, `langchain_core`
  - `requests`
  - `naas_abi_core` (for `logger` and `ChatModel`)
- Runtime dependency:
  - A local Docker Model Runner compatible with an OpenAI-style endpoint at:
    - `http://localhost:12434/engines/v1/chat/completions`

## Usage
### Non-streaming generation
```python
from langchain_core.messages import HumanMessage
from naas_abi.models.airgap_gemma import model

llm = model.model  # AirgapChatOpenAI instance
res = llm.invoke([HumanMessage(content="Write a one-line haiku about latency.")])
print(res.content)
```

### Streaming tokens
```python
from langchain_core.messages import HumanMessage
from naas_abi.models.airgap_gemma import model

llm = model.model
for chunk in llm.stream([HumanMessage(content="Count from 1 to 5.")]):
    print(chunk.content, end="")
print()
```

## Caveats
- Tool support is intentionally minimal:
  - `bind_tools()` does not store or apply tools.
  - `_generate()` forces `tool_calls = []` on the returned message.
- Streaming is implemented via `requests.post(..., stream=True)` and expects SSE-like `data:` lines and a `[DONE]` sentinel.
- If no valid user message is found, the wrapper substitutes `"Hello"`.
- Error handling during streaming yields an error chunk as model output (rather than raising).
