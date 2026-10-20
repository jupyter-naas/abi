# IntentAgent

## What it is
- An SDK routing agent that maps a user message to one or more **intents** using embedding similarity, optionally filters ambiguous matches with a chat model, optionally validates named-entity alignment (via spaCy if installed), then:
  - answers **RAW** intents directly,
  - injects **TOOL/AGENT** intents into the system prompt for downstream execution,
  - or asks the user to choose when multiple tool/agent intents are plausible.

## Public API

### `get_nlp() -> Any | None`
- Lazily loads `spacy.load("en_core_web_sm")` when available.
- Returns `None` if spaCy or the model is unavailable (no download attempted).

### `class IntentState(ABIAgentState)`
- State type for the graph.
- Adds: `intent_mapping: dict[str, Any]`.

### `class IntentAgent(Agent)`
Core intent-routing agent built on `langgraph`.

**Constructor**
```python
IntentAgent(
    name: str,
    description: str,
    chat_model: Any,
    embedding_model: Any | None = None,
    tools: list[Any] | None = None,
    agents: list[Any] | None = None,
    intents: list[Intent] | None = None,
    memory: Any = None,
    state: Any = None,
    configuration: Any = None,
    threshold: float = 0.85,
    threshold_neighbor: float = 0.05,
    direct_intent_score: float = 0.90,
    enable_default_intents: bool = True,
    enable_default_tools: bool = True,
    markdown_pretty_display: bool = True,
)
```
- Preprocesses provided intents:
  - For `IntentType.TOOL` / `IntentType.AGENT`: validates `intent_target` via `validate_name()` and forces `intent_scope = IntentScope.DIRECT`.
  - Optionally adds `DEFAULT_INTENTS` not overridden by user-provided intent values.
- Builds an `IntentMapper` for embedding-based retrieval.
- Accepts an embedding model; if it does **not** expose `aembed_query`, it will try `embedding_model.model` (SDK RemoteModel wrapper compatibility).

**Properties**
- `intents -> list[Intent]`: returns the prepared intents list.

**Graph / routing methods (used by the compiled LangGraph)**
- `build_graph() -> None`: compiles the internal `langgraph` state machine.
- `continue_conversation(state) -> Command`: routes to `"map_intents"`.
- `map_intents(state) -> Command`:
  - Uses `IntentMapper.map_intent(..., k=10)` with score thresholding.
  - Falls back to `IntentMapper.map_prompt` if no matches.
  - Applies `direct_intent_score` and `threshold_neighbor` logic to decide:
    - direct route to a single high-confidence intent,
    - or route to filtering / model fallback.
  - Special-case: if user replies with a digit after the agent asked to choose among multiple intents, it currently falls back to `"call_model"`.
- `should_filter(intents: list) -> str`: chooses `"intent_mapping_router"`, `"call_model"`, or `"filter_out_intents"`.
- `filter_out_intents(state) -> Command`:
  - Asks the chat model to call a tool (`filter_intents`) with a boolean list indicating which mapped intents to keep.
  - If tool parsing fails, keeps original mapped intents.
- `entity_check(state) -> Command`:
  - Extracts named entities from intent text and user message using spaCy if available.
  - If entities exist, may ask the chat model (must return `"true"`/`"false"`) whether the message refers to those entities.
- `intent_mapping_router(state) -> Command`:
  - If a single `RAW` intent: returns its `intent_target` as an `AIMessage` and ends.
  - If a single `AGENT` intent:
    - if target is not `"call_model"`, logs a warning (SDK has no local sub-agents here) and calls the model.
  - If multiple intents:
    - if multiple `TOOL/AGENT` intents: routes to human validation,
    - else injects intents into the system prompt.
- `request_human_validation(state) -> Command`:
  - Emits an `AIMessage` asking the user to pick an intent by number when multiple tool/agent intents exist.
- `inject_intents_in_system_prompt(state) -> Command | None`:
  - Adds or updates an `<intents_rules>` block and `<intents>` section inside the current `system_prompt` with mapped intents.

## Configuration/Dependencies
- **LangGraph**: `StateGraph`, `Command`, `START`, `END`.
- **LangChain Core**:
  - messages: `SystemMessage`, `HumanMessage`, `AIMessage`
  - tools: `langchain_core.tools.tool` (used for model-assisted filtering)
- **naas_abi_sdk**:
  - `Agent`, `ABIAgentState`
  - `IntentMapper`
  - `Intent`, `IntentType`, `IntentScope`, `DEFAULT_INTENTS`
  - `_messages.logger`, `_messages.validate_name`
- **Optional**: `spacy` with model `en_core_web_sm` for entity extraction.
  - If unavailable, entity checks are skipped (treated as entity-free).

## Usage
Minimal example (construct agent and build its graph):

```python
from naas_abi_sdk.agents.intent_agent import IntentAgent
from naas_abi_sdk.agents.intents import Intent, IntentType

# chat_model must support .ainvoke(...) and (for filtering) .bind_tools(...).ainvoke(...)
# embedding_model should support .aembed_query(...) (or be a wrapper exposing .model)
chat_model = ...
embedding_model = ...

intents = [
    Intent(intent_value="Say hello", intent_type=IntentType.RAW, intent_target="Hello!"),
]

agent = IntentAgent(
    name="intent_router",
    description="Routes messages to intents",
    chat_model=chat_model,
    embedding_model=embedding_model,
    intents=intents,
)

agent.build_graph()
# Execution depends on the surrounding Agent base class and runtime that feeds state/messages.
```

## Caveats
- spaCy entity extraction is **optional**; if spaCy or `en_core_web_sm` is missing, entity filtering becomes a no-op.
- When multiple tool/agent intents are presented and the user selects a number, this SDK variant currently routes to `"call_model"` rather than resolving a local sub-agent/tool selection.
- `inject_intents_in_system_prompt` assumes `state["system_prompt"]` exists and is a string.
