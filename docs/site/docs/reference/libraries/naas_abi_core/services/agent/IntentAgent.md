# IntentAgent

## What it is
`IntentAgent` is an `Agent` implementation that maps the latest user message to one or more predefined intents, optionally filters/validates them, and then routes execution to:
- a sub-agent,
- a tool call (via prompt injection + model/tool execution), or
- a raw text response.

It uses:
- vector-based intent mapping (`IntentMapper`),
- optional LLM-based filtering (`filter_out_intents`),
- spaCy NER + optional LLM checks for entity consistency (`entity_check`),
- a LangGraph `StateGraph` to orchestrate routing.

## Public API

### Functions
- `get_nlp() -> Any`
  - Lazily loads spaCy model `en_core_web_sm` (downloads it if missing) and caches it globally.

### Constants
- `MULTIPLES_INTENTS_MESSAGE: str`
  - Marker string used to detect the “multiple intents” validation message.

### Classes

#### `IntentState(ABIAgentState)`
State container extending the agent state with:
- `intent_mapping: Dict[str, Any]` — stores `{"intents": [...]}` where each item is a match dict (includes `score`, `text`, and `intent` object).

#### `IntentAgent(Agent)`
Core intent-routing agent.

**Constructor**
- `IntentAgent.__init__(...)`
  - Key params:
    - `chat_model: BaseChatModel | ChatModel` (required)
    - `embedding_model: Embeddings | None` (optional, passed to `IntentMapper`)
    - `tools: list[Tool | BaseTool | Agent]` (optional)
    - `agents: list[Agent]` (optional) — sub-agents to route to
    - `intents: list[Intent]` (optional) — custom intents
    - `memory: BaseCheckpointSaver | None` (optional) — if `None`, uses `create_checkpointer()`
    - `threshold: float` — minimum score to consider an intent (default `0.85`)
    - `threshold_neighbor: float` — max score gap from best intent to keep as “close” (default `0.05`)
    - `direct_intent_score: float` — score to allow direct routing when clearly best (default `0.90`)
    - `enable_default_intents: bool` — whether to add `DEFAULT_INTENTS` (default `True`)
    - `enable_default_tools: bool` — forwarded to base `Agent` (default `True`)

**Properties**
- `intents -> list[Intent]` — the agent’s effective intent list (custom + optional defaults).

**Graph / orchestration**
- `build_graph(patcher: Optional[Callable] = None) -> None`
  - Builds and compiles the LangGraph flow for intent mapping and routing.
  - Optionally allows modifying the graph before compilation via `patcher(graph)`.

**Conversation flow nodes (methods used as LangGraph nodes)**
- `continue_conversation(state) -> Command`
  - Routes to `map_intents`.

- `map_intents(state: IntentState) -> Command`
  - Maps the last user message to intents via `IntentMapper`.
  - Special handling: if the last assistant message asked for a numeric choice (multiple intents), a numeric user reply routes directly to the selected agent.
  - Applies score thresholding and neighbor filtering, deduplicates by intent target.

- `should_filter(intents: list) -> str`
  - Decides next node:
    - `call_model` if no intents,
    - `intent_mapping_router` if a single strong intent,
    - otherwise `filter_out_intents`.

- `filter_out_intents(state: IntentState) -> Command`
  - Uses the chat model with a temporary tool `filter_intents(bool_list)` to remove logically irrelevant intents.
  - On errors, falls back to `entity_check`.
  - Routes to `intent_mapping_router` when a single remaining intent is above threshold; otherwise routes to `entity_check`.

- `entity_check(state: IntentState) -> Command`
  - Uses spaCy NER to extract entities from each intent’s `intent_value` and from the user message.
  - If entities don’t clearly match, asks the LLM to output strictly `"true"`/`"false"` to decide whether to keep that intent.
  - Returns an update command with filtered intents (does not explicitly `goto` another node).

- `intent_mapping_router(state: IntentState) -> Command`
  - Routes based on mapped intents:
    - none: `call_model`
    - single RAW: ends and outputs `intent_target` as assistant message
    - single AGENT: routes to sub-agent node (and sets current active agent unless target is `"call_model"`)
    - single TOOL: routes to `inject_intents_in_system_prompt`
    - multiple: if >1 agent/tool intents, routes to `request_human_validation`, else `inject_intents_in_system_prompt`

- `request_human_validation(state: IntentState) -> Command`
  - When multiple agent/tool intents exist, emits a numbered list and ends the graph (`END`), waiting for user numeric selection in the next turn.

- `inject_intents_in_system_prompt(state: IntentState) -> Command | None`
  - Injects/updates an `<intents_rules>` block in `state["system_prompt"]`, including an `<intents>` list mapping each intent to its tool/target.
  - Returns a `Command(update={"system_prompt": ...})` when it injects; otherwise returns nothing.

**Utilities**
- `duplicate(queue: Queue | None = None, agent_shared_state: AgentSharedState | None = None) -> IntentAgent`
  - Creates another `IntentAgent` with the same configuration, duplicating sub-agents recursively and sharing/overriding queue/state as provided.

## Configuration/Dependencies
- **spaCy**
  - Requires model: `en_core_web_sm`.
  - If missing, `get_nlp()` downloads it at runtime (`spacy.cli.download`), requiring internet access.

- **LangGraph / LangChain**
  - Uses `StateGraph`, `Command`, `MessagesState`, and chat model tool-binding (`bind_tools`) for LLM-based filtering.

- **naas_abi_core**
  - Depends on base `Agent` framework, `IntentMapper`, and `DEFAULT_INTENTS`.

- **Checkpointing**
  - If `memory` is not provided, it uses `create_checkpointer()` (implementation not shown here).

## Usage
Minimal setup (requires your concrete chat model and intent definitions from the surrounding package):

```python
from naas_abi_core.services.agent.IntentAgent import IntentAgent
from naas_abi_core.services.agent.beta.IntentMapper import Intent, IntentType, IntentScope

# Provide a LangChain-compatible chat model instance (BaseChatModel)
chat_model = ...  # e.g., ChatOpenAI(...)

intents = [
    Intent(
        intent_value="Summarize the user's text",
        intent_type=IntentType.TOOL,
        intent_target="summarize",  # must correspond to an available tool name
        intent_scope=IntentScope.DIRECT,
    ),
]

agent = IntentAgent(
    name="router",
    description="Routes to tools/agents based on intent mapping",
    chat_model=chat_model,
    intents=intents,
)

agent.build_graph()
```

## Caveats
- `tools: list = []`, `agents: list = []`, `intents: list = []` are mutable default arguments in `__init__` (shared across instances if mutated externally).
- `entity_check()` returns a `Command` without an explicit `goto`; correct continuation depends on how the underlying graph handles node return values and edges (not shown in this file).
- The LLM-based parts assume:
  - tool-calling support for `filter_out_intents()` (`bind_tools`),
  - strict `"true"`/`"false"` output compliance for `entity_check()` decisions.
