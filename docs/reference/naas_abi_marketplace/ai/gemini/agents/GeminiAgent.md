# GeminiAgent

## What it is
An `IntentAgent` specialization that wires up Google Gemini (`gemini-2.5-flash`) with:
- A predefined system prompt (with tool descriptions injected)
- Image generation/storage tools from `ImageGenerationStorageWorkflow`
- A set of intents routing multimodal analysis to the model and image requests to a tool

## Public API

### Constants
- `NAME`: `"Gemini"`
- `DESCRIPTION`: Agent description string
- `AVATAR_URL`: Avatar image URL
- `SYSTEM_PROMPT`: System prompt template containing a `[TOOLS]` placeholder
- `SUGGESTIONS`: List of `{label, value}` suggestion templates

### Functions
- `create_agent(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> IntentAgent | None`
  - Builds and returns a configured `GeminiAgent`.
  - Fetches `gemini_api_key` from `naas_abi_marketplace.ai.gemini.ABIModule` configuration.
  - Loads chat model via `model_registry.get_chat_model("gemini-2.5-flash")`.
  - Instantiates `ImageGenerationStorageWorkflow` and appends its `as_tools()` to the agent tools.
  - Defines intents:
    - Multimodal analysis intents route to `IntentType.AGENT` with target `"call_model"`.
    - Image generation intents route to `IntentType.TOOL` with target `"generate_and_store_image"`.
  - Injects tool names/descriptions into `SYSTEM_PROMPT`.
  - Defaults:
    - `AgentConfiguration(system_prompt=...)` when `agent_configuration` is `None`
    - `AgentSharedState(thread_id="0")` when `agent_shared_state` is `None`
  - Sets `memory=None`.

### Classes
- `class GeminiAgent(IntentAgent)`
  - No additional behavior; inherits everything from `IntentAgent`.

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentAgent`, `IntentType`
- Requires Gemini module configuration:
  - `naas_abi_marketplace.ai.gemini.ABIModule.get_instance().configuration.gemini_api_key`
- Uses Gemini chat model via:
  - `ABIModule.get_instance().engine.services.model_registry.get_chat_model("gemini-2.5-flash")`
- Image tooling provided by:
  - `ImageGenerationStorageWorkflow`
  - `ImageGenerationStorageWorkflowConfiguration(gemini_api_key=...)`

## Usage
```python
from naas_abi_marketplace.ai.gemini.agents.GeminiAgent import create_agent

agent = create_agent()
# agent is an IntentAgent configured with a Gemini chat model, tools, and intents.
```

## Caveats
- Agent creation relies on `ABIModule` being properly configured with `gemini_api_key`.
- Image-generation intents assume a tool named `generate_and_store_image` is present (provided by `ImageGenerationStorageWorkflow.as_tools()`).
- `create_agent()` returns `IntentAgent | None` by type hint, but this module always returns a `GeminiAgent` if no exception occurs.
