# GeminiAgent

## What it is
A thin wrapper around `naas_abi_core.services.agent.IntentAgent` that configures a “Gemini” intent-based agent with:
- A predefined system prompt and suggestions metadata
- A Google Gemini chat model (`google_gemini_2_5_flash`)
- Image generation/storage tools exposed via a workflow
- A set of intents mapping user phrases to either the model or a tool

## Public API

### Constants
- `NAME`: Display name (`"Gemini"`).
- `DESCRIPTION`: Human-readable description of the agent.
- `AVATAR_URL`: Avatar image URL.
- `SYSTEM_PROMPT`: Base system prompt template containing a `[TOOLS]` placeholder.
- `SUGGESTIONS`: UI/UX suggestion templates (list of `{label, value}`).

### Functions
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Optional[IntentAgent]`
  - Builds and returns a configured `GeminiAgent`.
  - Injects available tool names/descriptions into `SYSTEM_PROMPT`.
  - Registers intents for multimodal analysis (handled by the model) and image generation (handled by a tool named `generate_and_store_image`).

### Classes
- `class GeminiAgent(IntentAgent)`
  - No additional behavior; inherits all functionality from `IntentAgent`.

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent` types:
  - `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentAgent`, `IntentType`
- Loads module configuration:
  - `from naas_abi_marketplace.ai.gemini import ABIModule`
  - Uses `module.configuration.gemini_api_key`
- Uses model:
  - `from naas_abi_marketplace.ai.gemini.models.google_gemini_2_5_flash import model`
- Adds tools via workflow:
  - `ImageGenerationStorageWorkflow` and `ImageGenerationStorageWorkflowConfiguration`
  - Tools are appended from `image_workflow.as_tools()`
- Defaulting behavior:
  - If `agent_configuration` is `None`, creates `AgentConfiguration(system_prompt=...)`
  - If `agent_shared_state` is `None`, creates `AgentSharedState(thread_id="0")`
  - `memory=None` is passed to the agent

## Usage
```python
from naas_abi_marketplace.ai.gemini.agents.GeminiAgent import create_agent

agent = create_agent()
# agent is an IntentAgent (GeminiAgent) configured with model, tools, and intents.
```

## Caveats
- `create_agent()` requires the Gemini module configuration to provide `gemini_api_key`; if missing/misconfigured, agent creation may fail at runtime.
- The set of tools injected into the system prompt depends on `ImageGenerationStorageWorkflow.as_tools()`, and image generation intents target a tool named `generate_and_store_image`.
