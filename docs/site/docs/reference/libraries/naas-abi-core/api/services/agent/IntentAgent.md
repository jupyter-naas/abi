# IntentAgent

## What it is
- An `Agent` implementation that maps the last user message to one or more predefined **intents**, then **routes** execution to:
  - a raw response (direct text),
  - a tool call,
  - a sub-agent,
  - or the base model fallback.
- Adds LLM-based intent filtering and spaCy-based entity validation to reduce false matches.

## Public API

### Functions
- `get_nlp() -> spacy.Language`
  - Lazily loads `en_core_web_sm` spaCy model; downloads it if missing.

### Classes
- `IntentState(ABIAgentState)`
  - Agent state extension that includes:
    - `intent_mapping: Dict[str, Any]` (intent analysis results)

- `IntentAgent(Agent)`
  - Intent-aware agent that builds a LangGraph flow and routes messages based on mapped intents.

#### Key properties
- `IntentAgent.intents -> list[Intent]`
  - Returns the internal list of intents used by the mapper (includes defaults and optional dev intents).

#### Key methods
- `__init__(..., intents: list[Intent]=[], agents: list[Agent]=[], tools: list=..., memory: BaseCheckpointSaver|None=None, threshold=0.85, threshold_neighbor=0.05, direct_intent_score=0.95, embedding_model: Embeddings | None = None)`
  - Initializes intent mapper, adds a built-in tool (`list_available_agents`), merges `DEFAULT_INTENTS` (+ `DEV_INTENTS` when `ENV != "prod"`), configures thresholds, and sets up memory/checkpointing.
  - Forwards `embedding_model` to `IntentMapper`; if omitted, mapper logs a warning and uses `OpenAIEmbeddings(model="text-embedding-3-large")`.
- `build_graph(patcher: Optional[Callable]=None) -> None`
  - Builds and compiles the internal LangGraph flow for routing.
- `duplicate(queue: Queue|None=None, agent_shared_state: AgentSharedState|None=None) -> IntentAgent`
  - Creates a new instance with duplicated sub-agents and independent shared state (but reuses configured tools/intents).

#### Graph node methods (used internally by the compiled graph)
- `continue_conversation(state) -> Command`
  - Routes to `map_intents`.
- `map_intents(state: IntentState) -> Command`
  - Maps last human message to intents via `IntentMapper` and thresholds; may route directly when a single high-confidence match exists; supports numeric selection after a multiple-intents validation prompt.
- `filter_out_intents(state: IntentState) -> Command`
  - Uses the chat model + a tool-call contract to remove logically irrelevant intents.
- `entity_check(state: IntentState) -> Command`
  - Uses spaCy entity extraction and (when needed) an LLM boolean check to filter intents whose entities aren’t supported by the conversation.
- `intent_mapping_router(state: IntentState) -> Command`
  - Routes based on intent count/type:
    - `RAW` → returns the raw target text and ends.
    - `AGENT` → routes to sub-agent or `call_model`.
    - `TOOL` → injects intent rules and proceeds to model/tool calling path.
    - multiple tool/agent intents → asks user to choose.
- `request_human_validation(state: IntentState) -> Command`
  - Prompts user to choose among multiple candidate tool/agent intents by number.
- `inject_intents_in_system_prompt(state: IntentState) -> Command|None`
  - Adds/updates an `<intents_rules>` section in `state["system_prompt"]` listing mapped intents.

## Configuration/Dependencies
- Environment:
  - `ENV`: if not equal to `"prod"`, `DEV_INTENTS` are appended.
  - Memory/checkpointer: if `memory is None`, uses `create_checkpointer()` (implementation in `.Agent`; may use PostgreSQL depending on environment such as `POSTGRES_URL` per docstring).
- External libraries:
  - `spaCy` with model `en_core_web_sm` (auto-downloaded on first use).
  - `langgraph` for `StateGraph` compilation and routing.
  - `langchain_core` message/tool/model abstractions.
  - `pydash` for list searching/filtering.
- Intent mapping:
  - Uses `IntentMapper` from `.beta.IntentMapper`.

## Usage

```python
from naas_abi_core.services.agent.IntentAgent import IntentAgent
from langchain_openai import OpenAIEmbeddings
from naas_abi_core.models.Model import ChatModel  # or any langchain BaseChatModel

# Provide a chat model compatible with langchain_core BaseChatModel
chat_model = ChatModel()  # depends on your project configuration

agent = IntentAgent(
    name="intent-router",
    description="Routes user requests by intent",
    chat_model=chat_model,
    agents=[],   # optional sub-agents
    tools=[],    # optional tools; IntentAgent adds list_available_agents automatically
    intents=[],  # optional custom intents; defaults are appended
    embedding_model=OpenAIEmbeddings(model="text-embedding-3-large"),
)

agent.build_graph()

# Execution entrypoints are defined in the base Agent class (not shown in this file).
# Use the base Agent's run/invoke method appropriate to your project.
```

## Caveats
- spaCy model download:
  - If `en_core_web_sm` is not installed, the agent will download it at runtime on first entity extraction, requiring internet access.
- Mutable defaults in `__init__`:
  - The signature uses `tools=[]`, `agents=[]`, `intents=[]`. These lists are mutated (e.g., `tools.append(...)`, `intents.append(...)`), which can leak state across instances if the same default list object is reused by Python. Prefer passing explicit new lists when instantiating.
- Multiple-intent selection:
  - Numeric selection routing only triggers when the last AI message contains `MULTIPLES_INTENTS_MESSAGE` and has `additional_kwargs["owner"] == self.name`.
