# ChatGPTAgent

## What it is
`ChatGPTAgent` is an `IntentAgent` that routes user requests to:
- web search (`chatgpt_search_web`)
- image analysis (`chatgpt_analyze_image`)
- PDF analysis (`chatgpt_analyze_pdf`)
- or the underlying chat model (`call_model`) for general assistance.

It defines a system prompt and a set of intent rules for tool/agent/raw responses.

## Public API

### Class: `ChatGPTAgent(IntentAgent)`
Class attributes:
- `name`: `"ChatGPT"`
- `description`: Describes capabilities (real-time answers, image/PDF analysis).
- `logo_url`: Public URL to an image.
- `system_prompt`: System instructions for tool selection and response handling.
- `intents: list[Intent]`: Maps intent phrases to:
  - `IntentType.TOOL` targets: `chatgpt_search_web`, `chatgpt_analyze_image`, `chatgpt_analyze_pdf`
  - `IntentType.AGENT` target: `call_model`
  - `IntentType.RAW` target: a Markdown block linking to OpenAI Models documentation

Methods:
- `get_tools() -> list` (static)
  - Builds and returns tool definitions via `OpenAIResponsesIntegration`.
  - Chooses provider endpoint based on `ABIModule` configuration:
    - OpenAI default: `https://api.openai.com/v1/responses`
    - OpenRouter override (if `openrouter_api_key` is set): `https://openrouter.ai/api/v1/responses`
- `get_model() -> ChatModel` (static)
  - Retrieves a chat model from the module’s model registry using `CanonicalModelId.GPT_5_2`.
- `New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> IntentAgent` (class method)
  - Factory that returns a configured `ChatGPTAgent`.
  - Defaults:
    - `AgentConfiguration(system_prompt=ChatGPTAgent.system_prompt)`
    - `AgentSharedState(thread_id="0")`
  - Sets `memory=None`.

## Configuration/Dependencies
- `naas_abi_core`:
  - `IntentAgent`, `Intent`, `IntentType`
  - `AgentConfiguration`, `AgentSharedState`
  - `ChatModel`, `CanonicalModelId`
- `naas_abi_marketplace.ai.chatgpt`:
  - `ABIModule.get_instance()` providing configuration:
    - `openai_api_key`
    - `openrouter_api_key` (optional override)
  - `OpenAIResponsesIntegrationConfiguration` and `as_tools(...)` to construct tools

## Usage
```python
from naas_abi_marketplace.ai.chatgpt.agents.ChatGPTAgent import ChatGPTAgent

agent = ChatGPTAgent.New()
```

## Caveats
- `get_tools()` depends on `ABIModule` being configured with a valid API key (`openai_api_key` or `openrouter_api_key`), otherwise tool initialization may fail.
- The default shared state uses `thread_id="0"` unless overridden.
