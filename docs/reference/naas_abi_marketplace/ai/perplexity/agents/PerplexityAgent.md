# PerplexityAgent

## What it is
A thin `IntentAgent` configuration wrapper that builds an agent named **Perplexity** for real-time web research using Perplexity tooling and intent-based routing.

## Public API
- `create_agent(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> IntentAgent`
  - Creates and returns a configured `PerplexityAgent`:
    - Chat model: retrieved from the Perplexity `ABIModule` model registry as `"sonar-pro-search"`.
    - Tools: registered via `PerplexityIntegration.as_tools(...)` using a `PerplexityIntegrationConfiguration`.
    - Intents: maps common “search …” phrases to Perplexity tools:
      - `perplexity_quick_search` for `"quick search about"`
      - `perplexity_search` for `"search news about"`, `"search web about"`, `"search information about"`
      - `perplexity_advanced_search` for `"advanced search about"`, `"search web with high context size about"`
      - Raw response for `"where can i find information about perplexity models"` pointing to Perplexity model docs.
    - Defaults:
      - `AgentConfiguration(system_prompt=SYSTEM_PROMPT)` if none provided
      - `AgentSharedState(thread_id="0")` if none provided
    - Agent calling is disabled: `agents=[]`.

- `class PerplexityAgent(IntentAgent)`
  - Empty subclass of `IntentAgent` (inherits all behavior).

## Configuration/Dependencies
- Core agent framework:
  - `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentAgent`, `IntentType` from `naas_abi_core.services.agent.IntentAgent`.
- Perplexity module and integration:
  - `naas_abi_marketplace.ai.perplexity.ABIModule`
    - Uses `ABIModule.get_instance().configuration.perplexity_api_key` for API access.
    - Uses `abi_module.engine.services.model_registry.get_chat_model("sonar-pro-search")`.
  - `PerplexityIntegrationConfiguration`, `as_tools` from `naas_abi_marketplace.ai.perplexity.integrations.PerplexityIntegration`.

## Usage
```python
from naas_abi_marketplace.ai.perplexity.agents.PerplexityAgent import create_agent

agent = create_agent()

# Interact with `agent` using the IntentAgent interface provided by naas_abi_core.
# (Exact invocation depends on the surrounding agent runtime.)
```

## Caveats
- `PerplexityAgent` adds no methods; behavior is entirely inherited from `IntentAgent`.
- Correct operation requires `perplexity_api_key` to be set in the Perplexity `ABIModule` configuration.
- Agent-to-agent calling is explicitly disabled (`agents=[]`).
