# ChatGPTAgent

## What it is
`ChatGPTAgent` is an `IntentAgent` implementation that routes user intents to:
- a web search tool,
- an image analysis tool,
- a PDF analysis tool,
or to a chat model for general assistance.

It also exposes a predefined system prompt and intent mappings for tool/agent/raw responses.

## Public API

### Class: `ChatGPTAgent(IntentAgent)`
Operator-facing attributes (class-level):
- `name`: `"ChatGPT"`
- `description`: human-readable description of capabilities.
- `logo_url`: URL to an agent logo image.
- `system_prompt`: system instructions guiding tool selection and response handling.
- `intents`: list of `Intent` rules mapping phrases to:
  - `IntentType.TOOL` targets: `chatgpt_search_web`, `chatgpt_analyze_image`, `chatgpt_analyze_pdf`
  - `IntentType.AGENT` target: `call_model`
  - `IntentType.RAW` target: a Markdown link to OpenAI Models documentation

Methods:
- `get_tools(cls) -> list` (static):
  - Builds tool definitions via `OpenAIResponsesIntegration` and returns them.
  - Selects provider endpoint based on module configuration (OpenAI vs OpenRouter).
- `get_model(cls) -> ChatModel` (static):
  - Returns the chat model used by the agent (`gpt_4_1_mini` model object).
- `New(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent` (class method):
  - Factory that constructs and returns a configured `ChatGPTAgent`.
  - Defaults:
    - `AgentConfiguration(system_prompt=ChatGPTAgent.system_prompt)`
    - `AgentSharedState(thread_id="0")`
  - Sets `memory=None`.

## Configuration/Dependencies
- Depends on `naas_abi_core`:
  - `IntentAgent`, `Intent`, `IntentType`, `AgentConfiguration`, `AgentSharedState`
  - `ChatModel`
- Depends on `naas_abi_marketplace.ai.chatgpt`:
  - `ABIModule.get_instance()` configuration values:
    - `openai_api_key` (default)
    - `openrouter_api_key` (if set, overrides API key and base URL)
  - `OpenAIResponsesIntegrationConfiguration` + `as_tools(...)`
  - Model import: `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini.model`
- Tool endpoint selection:
  - OpenAI: `https://api.openai.com/v1/responses`
  - OpenRouter: `https://openrouter.ai/api/v1/responses` (when `openrouter_api_key` is present)

## Usage
```python
from naas_abi_marketplace.ai.chatgpt.agents.ChatGPTAgent import ChatGPTAgent

agent = ChatGPTAgent.New()
# agent is an IntentAgent instance configured with model, tools, intents, and state.
```

## Caveats
- `get_tools()` requires `ABIModule` to be properly configured with an API key (`openai_api_key` or `openrouter_api_key`), otherwise tool initialization may fail.
- The default `AgentSharedState` uses `thread_id="0"` unless you provide your own state.
