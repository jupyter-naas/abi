# StripeAgent

## What it is
A Stripe-focused `IntentAgent` implementation that provides **general guidance** about Stripe (payments, subscriptions, financial operations). It is configured with **no Stripe tools**, so it cannot perform real Stripe actions.

## Public API
- `class StripeAgent(IntentAgent)`
  - Agent definition with default metadata:
    - `name = "Stripe"`
    - `description = "Helps you interact with Stripe for payment processing and financial operations."`
    - `system_prompt`: guidance-only prompt (explicitly states tools are unavailable)
    - `suggestions = []`
- `StripeAgent.New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> StripeAgent`
  - Factory constructor that:
    - Retrieves default chat and embedding models from the application `ModelRegistryService`.
    - Configures:
      - `tools = []`
      - `intents`: two `IntentType.RAW` intents for common Stripe questions
    - Applies defaults when not provided:
      - `agent_configuration = AgentConfiguration(system_prompt=StripeAgent.system_prompt)`
      - `agent_shared_state = AgentSharedState(thread_id="0")`

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `Intent`, `IntentType`, `AgentConfiguration`, `AgentSharedState`
- Depends on application module:
  - `from naas_abi_marketplace.applications.stripe import ABIModule`
  - Uses `ABIModule.get_instance().engine.services.model_registry`:
    - `get_default_chat_model()`
    - `get_default_embedding_model().model`
- Requires `ModelRegistryService` to be initialized; otherwise raises via:
  - `assert registry is not None, "ModelRegistryService not initialized"`

## Usage
```python
from naas_abi_marketplace.applications.stripe.agents.StripeAgent import StripeAgent

agent = StripeAgent.New()
print(agent.name)         # Stripe
print(agent.description)  # Helps you interact with Stripe for payment processing...
```

## Caveats
- No tools are configured (`tools = []`), so the agent cannot execute Stripe operations (e.g., create charges, manage customers/subscriptions). It can only provide informational guidance.
- `StripeAgent.New()` requires the Stripe `ABIModule` engine and model registry to be initialized; otherwise initialization will fail with an assertion error.
