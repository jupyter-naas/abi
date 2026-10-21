# GitHubAgentIntents

## What it is
A module that defines a constant list of GitHub-related `Intent` definitions (`INTENTS`) for an intent-driven agent system. Each intent maps a human-readable intent description to a tool target name.

## Public API
- `INTENTS: list`
  - A list of `Intent` objects describing available GitHub tool intents.
  - Each `Intent` is created with:
    - `intent_value`: description of the intent
    - `intent_type`: `IntentType.TOOL`
    - `intent_target`: tool identifier string (e.g., `"github_get_user_details"`)

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.services.agent.IntentAgent.Intent`
  - `naas_abi_core.services.agent.IntentAgent.IntentType`

No runtime configuration is defined in this file.

## Usage
```python
from naas_abi_marketplace.applications.github.agents.intents.GitHubAgentIntents import INTENTS

# Inspect available intent targets
targets = [i.intent_target for i in INTENTS]
print(targets)
```

## Caveats
- This module only declares intents; it does not implement the underlying tools referenced by `intent_target`.
