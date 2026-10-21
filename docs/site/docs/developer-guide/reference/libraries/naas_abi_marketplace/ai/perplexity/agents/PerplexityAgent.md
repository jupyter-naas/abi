# PerplexityAgent

## What it is
A thin `IntentAgent` wrapper that configures a “Perplexity” research/search agent, wiring Perplexity search tools and intent routing to those tools.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Builds and returns a configured `PerplexityAgent` instance:
    - Uses a GPT-4.1 chat model (`naas_abi_marketplace.ai.chatgpt.models.gpt_4_1`).
    - Registers Perplexity tools via `PerplexityIntegration.as_tools(...)`.
    - Defines `Intent` mappings that route common “search …” requests to specific tools.
    - Applies defaults for `AgentConfiguration` (system prompt) and `AgentSharedState` (thread id `"0"`).

- `class PerplexityAgent(IntentAgent)`
  - No additional behavior beyond `IntentAgent` (empty subclass).

## Configuration/Dependencies
- Requires Perplexity API key from:
  - `naas_abi_marketplace.ai.perplexity.ABIModule.get_instance().configuration.perplexity_api_key`
- Uses Perplexity integration tooling:
  - `PerplexityIntegrationConfiguration`
  - `as_tools(...)` to create tools (e.g., `perplexity_quick_search`, `perplexity_search`, `perplexity_advanced_search`)
- Uses core agent framework types:
  - `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentAgent`, `IntentType` from `naas_abi_core.services.agent.IntentAgent`

## Usage
```python
from naas_abi_marketplace.ai.perplexity.agents.PerplexityAgent import create_agent

agent = create_agent()
# Use `agent` according to the IntentAgent interface in naas_abi_core.
```

## Caveats
- `PerplexityAgent` itself adds no methods; all behavior is inherited from `IntentAgent`.
- Agent-to-agent calling is explicitly disabled here (`agents=[]`), with a note indicating it’s not available for Perplexity in LangChain.
- Correct operation depends on the Perplexity API key being present in the module configuration.
