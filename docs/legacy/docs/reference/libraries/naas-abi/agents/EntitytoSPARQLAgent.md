# EntitytoSPARQLAgent

## What it is
- A LangGraph/LangChain-based agent that:
  - Extracts entities from an input text using BFO (Basic Formal Ontology) mappings.
  - Fetches possible object properties for the extracted entity classes from a triple store.
  - Generates a SPARQL `INSERT DATA` statement representing entities and relationships.
  - Saves intermediate artifacts (original text, entities JSON, object properties JSON, SPARQL) to object storage.

## Public API

### Module-level constants
- `NAME`: `"Entity_to_SPARQL"`
- `DESCRIPTION`: Agent description string.
- `SYSTEM_PROMPT`: Long ontology-engineering prompt used as default system prompt.

### Functions
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Optional[Agent]`
  - Factory that constructs and returns an `EntitytoSPARQLAgent` using the default model (`naas_abi.models.default.get_model()`), `MemorySaver` checkpointer, and provided (or new) shared state/configuration.

### Classes
- `EntityExtractionState(ABIAgentState)`
  - Agent state extension with:
    - `entities: list[dict[str, Any]]`
    - `object_properties: list[dict[str, Any]]`

- `EntitytoSPARQLAgent(Agent)`
  - Core agent implementation.
  - Key methods (graph nodes):
    - `entity_extract(state: EntityExtractionState) -> Command`
      - Calls the chat model with a dedicated extraction prompt and updates `messages` with the model response (expected to be JSON).
    - `prep_data(state: EntityExtractionState) -> Command`
      - Parses JSON entities from the last model message.
      - Adds a generated ABI URI (`http://ontology.naas.ai/abi/<uuid>`) to each entity.
      - Queries object properties per distinct `class_uri` via `GetObjectPropertiesFromClassWorkflow`.
      - Saves `init_text.txt`, `entities.json`, `object_properties.json` to object storage.
      - Updates state with `entities` and `object_properties`.
    - `create_sparql(state: EntityExtractionState) -> Command`
      - Calls the chat model to generate a SPARQL `INSERT DATA` statement from `entities`, `object_properties`, and the original message.
      - Saves `insert_data.sparql` to object storage.
      - Updates `messages` with an `AIMessage` containing the SPARQL.
    - `call_model(state: EntityExtractionState) -> Command`
      - Invokes the tool-capable model (`_chat_model_with_tools`) on the current messages (optionally prepending `state["system_prompt"]`).
      - Ends execution (`goto="__end__"`) with the response in `messages`.
    - `build_graph(patcher: Optional[Callable] = None)`
      - Builds and compiles the execution graph:
        - `START -> entity_extract -> prep_data -> create_sparql -> call_model`

## Configuration/Dependencies
- Requires a configured `ABIModule` engine and services:
  - `SERVICES.triple_store` (used by `GetObjectPropertiesFromClassWorkflow`)
  - `SERVICES.object_storage` (used by `StorageUtils`)
- Uses:
  - `langchain_core` (chat model + message types)
  - `langgraph` (StateGraph, Command, checkpointing)
  - `naas_abi_core` agent framework (`Agent`, `AgentSharedState`, `AgentConfiguration`, `ABIAgentState`)
  - `naas_abi_core.utils.JSON.extract_json_from_completion` for parsing model output
- Storage path:
  - `datastore/ontology/entities_to_sparql/<timestamp YYYYMMDDHHMMSS>`

## Usage

```python
from langchain_core.messages import AIMessage
from naas_abi.agents.EntitytoSPARQLAgent import create_agent

agent = create_agent()

# Build the internal graph (required before running, depending on Agent base implementation)
agent.build_graph()

# Provide input text as a message in the agent state and run the compiled graph
initial_state = {"messages": [AIMessage(content="Alice signed a contract with Bob yesterday.")]}

# If the base Agent exposes a LangGraph app, it's typically something like:
result = agent.graph.invoke(initial_state)

# The final SPARQL is stored in the last message content
print(result["messages"][-1].content)
```

## Caveats
- `entity_extract` expects the model to return **only JSON** (per prompt). `prep_data` will fail if JSON cannot be extracted from the last message.
- `prep_data` assumes `state["messages"][-2]` exists (used to save `init_text.txt`); the graph order must ensure there is an original message before the extraction response.
- SPARQL generation is model-driven; correctness depends on model compliance with the prompt constraints.
- Default constructor arguments use mutable defaults (`tools=[]`, `agents=[]`), which may cause shared state across instances if those lists are mutated.
