# NewsAPIAgent

## What it is
- An `IntentAgent` wrapper configured to provide **general guidance** about NewsAPI (features, search concepts, media monitoring).
- Ships with **no tools** for actually calling NewsAPI; it only returns predefined informational intents.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Factory that builds and returns a configured `NewsAPIAgent`.
  - Sets:
    - `name="NewsAPI"`, `description=...`
    - `system_prompt` (guidance-only; explicitly states tools are unavailable)
    - `tools=[]` (no integrations)
    - two RAW intents (feature info; search/retrieval concepts)
    - shared state and configuration (creates defaults if not provided)
- `class NewsAPIAgent(IntentAgent)`
  - Concrete agent type (no additional behavior; `pass`).

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Uses chat model import:
  - `from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1 import model`
- Key module constants:
  - `SYSTEM_PROMPT`: instructs the agent to provide guidance only and not retrieve content.
  - `SUGGESTIONS`: empty list.

## Usage
```python
from naas_abi_marketplace.applications.newsapi.agents.NewsAPIAgent import create_agent

agent = create_agent()

# The agent is configured with no tools; it can only provide general guidance via its intents/system prompt.
print(agent.name)
print(agent.description)
```

## Caveats
- No NewsAPI tools are configured (`tools=[]`), so the agent **cannot** fetch live articles or headlines.
- The built-in intents are informational (`IntentType.RAW`) and do not trigger external operations.
