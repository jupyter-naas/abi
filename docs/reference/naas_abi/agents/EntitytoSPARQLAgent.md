# EntitytoSPARQLAgent

## What it is
- A LangGraph/Naas ABI `Agent` that:
  - Extracts entities from an input message using a BFO-guided prompt.
  - Fetches candidate object properties for each extracted entity class from a triple store.
  - Generates a SPARQL `INSERT DATA` statement for the extracted entities and relationships.
  - Persists intermediate artifacts (original text, entities JSON, object properties JSON, generated SPARQL) to object storage.

## Public API

### Module-level constants
- `NAME`: Human-readable agent name (`"Entity to SPARQL"`).
- `DESCRIPTION`: Agent description.
- `SYSTEM_PROMPT`: Default system prompt used when no configuration is provided (high-level ontology engineer prompt).

### Functions
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Optional[Agent]`
  - Factory that constructs an `EntitytoSPARQLAgent` with:
    - Default model from `naas_abi.models.default.get_model()`
    - `MemorySaver()` checkpointer
    - Provided or default `AgentSharedState` and `AgentConfiguration` (default includes `SYSTEM_PROMPT`)

### Classes
- `EntityExtractionState(ABIAgentState)`
  - Agent state schema extension for this workflow.
  - Declares:
    - `entities: list[dict[str, Any]]`
    - `object_properties: list[dict[str, Any]]`

- `EntitytoSPARQLAgent(Agent)`
  - Main agent implementation.
  - Key methods (invoked via its compiled graph):
    - `entity_extract(state: EntityExtractionState) -> Command`
      - Calls the chat model with a specialized extraction prompt.
      - Updates state with the model response as a message (expects JSON in the response content).
    - `prep_data(state: EntityExtractionState) -> Command`
      - Parses JSON entities from the last model message.
      - Assigns a UUID-based `uri` to each entity.
      - Calls `GetObjectPropertiesFromClassWorkflow` for each unique `class_uri`.
      - Saves `init_text.txt`, `entities.json`, `object_properties.json` to object storage.
      - Updates state fields `entities` and `object_properties`.
    - `create_sparql(state: EntityExtractionState) -> Command`
      - Calls the chat model to produce a SPARQL `INSERT DATA` statement from:
        - `state.entities`
        - `state.object_properties`
        - an “original message” derived from `state["messages"][0].content`
      - Saves `insert_data.sparql` to object storage.
      - Updates state messages with the SPARQL as an `AIMessage`.
    - `call_model(state: EntityExtractionState) -> Command`
      - Calls the tool-enabled model (`self._chat_model_with_tools`) with messages (optionally prefixed by `state["system_prompt"]`).
      - Returns `Command(goto="__end__")` with the response message.
    - `build_graph(patcher: Optional[Callable] = None)`
      - Builds and compiles a `StateGraph(EntityExtractionState)` with the fixed sequence:
        - `START -> entity_extract -> prep_data -> create_sparql -> call_model`

## Configuration/Dependencies
- Relies on Naas ABI runtime singletons:
  - `ABIModule.get_instance().engine.services` (used for `triple_store` and `object_storage`)
- Storage:
  - Uses `StorageUtils(…object_storage…)` and writes under:
    - `datastore/ontology/entities_to_sparql/<YYYYMMDDHHMMSS>/`
- Triple store dependency:
  - `GetObjectPropertiesFromClassWorkflow` is instantiated with `triple_store=SERVICES.triple_store`
- Checkpointing:
  - Defaults to `MemorySaver()`
- Model:
  - `create_agent()` uses `naas_abi.models.default.get_model()`

## Usage
```python
from naas_abi.agents.EntitytoSPARQLAgent import create_agent

agent = create_agent()

# Typical Agent interface is provided by naas_abi_core.services.agent.Agent.Agent.
# The exact invocation method depends on that base class implementation.
# Common patterns include agent.run(...) or agent.invoke(...).
```

## Caveats
- `prep_data()` asserts that the last message content is a `str` and assumes it contains JSON parseable by `extract_json_from_completion()`.
- `prep_data()` accesses `state["messages"][-2]` to save `init_text.txt`; the workflow requires at least two messages in state at that point.
- `create_sparql()` uses `state["messages"][0].content` as the “original message”, which may not be the initial user text depending on how messages are seeded before execution.
- The code stores `object_properties` in state as `list(object_properties.values())` (not keyed by `class_uri`).
