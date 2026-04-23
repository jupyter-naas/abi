# StripeAgent

## What it is
A minimal `IntentAgent` factory and agent class for providing **general guidance about Stripe** (payments, subscriptions, features). This agent is explicitly configured with **no Stripe tools**, so it cannot perform real Stripe operations.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Builds and returns a configured `StripeAgent` instance.
  - Sets:
    - `name`: `"Stripe"`
    - `description`: Stripe guidance focus
    - `system_prompt`: explains tool unavailability and guidance-only constraints
    - `tools`: empty list
    - `intents`: two RAW intents for common Stripe questions
    - `chat_model`: imported from `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1`

- `class StripeAgent(IntentAgent)`
  - Concrete agent type; no additional behavior beyond `IntentAgent` (inherits everything).

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `Intent`, `IntentType`, `AgentConfiguration`, `AgentSharedState`
- Uses chat model from:
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1`
- Configuration:
  - `SYSTEM_PROMPT` is used by default if no `AgentConfiguration` is provided.
  - `SUGGESTIONS` is defined but unused.

## Usage
```python
from naas_abi_marketplace.applications.stripe.agents.StripeAgent import create_agent

agent = create_agent()

# The returned object is an IntentAgent/StripeAgent instance configured for guidance-only.
# Interact with it using the IntentAgent interfaces available in your runtime.
print(agent.name)         # "Stripe"
print(agent.description)  # Helps you interact with Stripe...
```

## Caveats
- No Stripe tools are configured (`tools = []`), so the agent:
  - cannot process payments,
  - cannot query customers/subscriptions,
  - can only provide general information and best-practice guidance.
