# SevenBucketsAgent

## What it is
An ontology-engineering chat agent factory for the **BFO “7 Buckets”** framework. It builds a `SevenBucketsAgent` (a thin subclass of `Agent`) configured with:
- A large system prompt embedding a Turtle template ontology.
- A tool to validate and save generated Turtle ontologies to a fixed ontologies directory.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Agent`
  - Creates and returns a configured `SevenBucketsAgent`.
  - Loads a Turtle template from `TEMPLATE_ONTOLOGY` and injects it into the system prompt.
  - Registers one tool: `save_ontology` (LangChain tool; return-direct).

- `class SevenBucketsAgent(Agent)`
  - No additional behavior beyond `Agent` (empty subclass).

## Configuration/Dependencies
- Constants
  - `NAME = "7_Buckets"`
  - `DESCRIPTION = "Converts a process into a valid ontology following the BFO 7 Buckets framework."`
  - `ONTOLOGIES_DIR = "libs/naas-abi-marketplace/naas_abi_marketplace/domains/ontology_engineer/ontologies"`
  - `TEMPLATE_ONTOLOGY = <ONTOLOGIES_DIR>/BFO7BucketsProcessOntology.ttl`
  - `SUGGESTIONS`: single canned prompt suggestion.
- External dependencies
  - `rdflib.Graph` for parsing/serializing Turtle and counting triples.
  - `langchain_core.tools.tool` for exposing `save_ontology` as a tool.
  - `naas_abi_core.services.agent.Agent` (`Agent`, `AgentConfiguration`, `AgentSharedState`)
  - Chat model import used by `create_agent`:
    - `from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1 import model`
- Filesystem behavior
  - Creates `ONTOLOGIES_DIR` if missing.
  - Writes `.ttl` files within `ONTOLOGIES_DIR`.

### Tool: `save_ontology`
Registered inside `create_agent` as a LangChain tool (`return_direct=True`).

Signature:
- `save_ontology(filename: str, turtle: str, overwrite: bool = False, encoding: str = "utf-8") -> str`

Behavior:
- Sanitizes `filename`:
  - Must be non-empty, no `/` or `\`, only letters/digits/`._-`, ensures `.ttl` suffix.
- Validates `turtle` by parsing with `rdflib` (`format="turtle"`).
- Serializes and writes normalized Turtle to `<ONTOLOGIES_DIR>/<filename>`.
- If file exists and `overwrite=False`, returns a message instead of writing.

## Usage
```python
from naas_abi_marketplace.domains.ontology_engineer.agents.SevenBucketsAgent import create_agent
from naas_abi_core.services.agent.Agent import AgentSharedState

agent = create_agent(agent_shared_state=AgentSharedState(thread_id="demo"))

# The agent exposes a tool named "save_ontology" via its tool system (implementation depends on Agent runtime).
# Typically, the LLM will call the tool after generating Turtle content.
```

## Caveats
- `create_agent()` parses `TEMPLATE_ONTOLOGY` at import-time execution; it will fail if the template file is missing or invalid Turtle.
- `save_ontology` enforces strict filename rules and forbids path separators (cannot write outside `ONTOLOGIES_DIR`).
- Turtle content must be valid; invalid Turtle raises during `rdflib` parsing.
