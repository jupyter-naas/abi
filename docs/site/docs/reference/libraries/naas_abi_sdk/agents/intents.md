# intents

## What it is
Defines intent primitives (scope/type + a dataclass) and a module-level `DEFAULT_INTENTS` list used to map common user utterances to agent/tool/raw responses. The file is explicitly copied to stay in parity with `naas_abi_core`.

## Public API
- `class IntentScope(Enum)`
  - `DIRECT`: intent applies to direct interactions.
  - `ALL`: intent applies to all scopes.
- `class IntentType(Enum)`
  - `AGENT`: route to an agent method (e.g., `"call_model"`).
  - `TOOL`: route to a tool method (e.g., `"list_tools_available"`).
  - `RAW`: return a raw/static response string.
- `@dataclass class Intent`
  - `intent_value: str`: user text to match.
  - `intent_type: IntentType`: classification of intent handling.
  - `intent_target: Any`: target handler identifier (commonly a string name) or raw response.
  - `intent_scope: IntentScope | None = IntentScope.ALL`: scope for intent applicability.
- `DEFAULT_INTENTS: list`
  - Predefined `Intent` instances for common greetings, thanks, and listing tools/sub-agents/intents.

## Configuration/Dependencies
- Standard library only:
  - `dataclasses.dataclass`
  - `enum.Enum`
  - `typing.Any`

## Usage
```python
from naas_abi_sdk.agents.intents import DEFAULT_INTENTS, IntentType, IntentScope

# Example: find a direct-match intent (exact string match)
user_text = "Hello"
intent = next(
    (i for i in DEFAULT_INTENTS if i.intent_value == user_text and i.intent_scope == IntentScope.DIRECT),
    None,
)

if intent and intent.intent_type == IntentType.RAW:
    print(intent.intent_target)  # static response string
```

## Caveats
- This module does not implement any matching logic beyond providing data; matching/dispatch must be done by the caller.
- `DEFAULT_INTENTS` entries are exact strings (case/punctuation sensitive).
- File is intended to remain synchronized with `naas_abi_core` equivalents; changes should be coordinated.
