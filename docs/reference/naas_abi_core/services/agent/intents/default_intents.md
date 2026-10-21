# DEFAULT_INTENTS

## What it is
A module-level list of predefined `Intent` objects used to map common user utterances (greetings, thanks, basic agent questions, and discovery commands) to an intent type/target within the agent system.

## Public API
- `DEFAULT_INTENTS: list`
  - A list of `Intent` instances with:
    - `intent_value`: the exact user phrase to match
    - `intent_type`: how the intent should be handled (`AGENT`, `RAW`, `TOOL`)
    - `intent_target`: handler name or raw response text (depending on type)
    - `intent_scope`: scope of matching (set to `IntentScope.DIRECT` for all entries)

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.beta.IntentMapper`:
  - `Intent`
  - `IntentScope`
  - `IntentType`

No additional configuration is defined in this file.

## Usage
```python
from naas_abi_core.services.agent.intents.default_intents import DEFAULT_INTENTS

# Example: list all trigger phrases
phrases = [i.intent_value for i in DEFAULT_INTENTS]
print(phrases)

# Example: find the intent definition for a given phrase
query = "Hello"
match = next((i for i in DEFAULT_INTENTS if i.intent_value == query), None)
print(match)
```

## Caveats
- Matching is phrase-based: `intent_value` entries are specific strings (e.g., `"Hello"` vs `"Hello there"`). This module does not implement normalization or fuzzy matching.
