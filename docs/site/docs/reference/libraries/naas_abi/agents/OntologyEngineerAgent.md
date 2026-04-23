# OntologyEngineerAgent

## What it is
An `Agent` factory and thin wrapper class that configures an “Ontology Engineer” agent specialized in BFO (Basic Formal Ontology) guidance and a text-to-ontology workflow by delegating work to sub-agents.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Optional[Agent]`
  - Creates and returns an `OntologyEngineerAgent` instance.
  - Responsibilities:
    - Loads the default chat model via `naas_abi.models.default.get_model()`.
    - Applies a default `AgentConfiguration(system_prompt=SYSTEM_PROMPT)` when none is provided.
    - Creates an `AgentSharedState` when none is provided.
    - Instantiates and attaches two sub-agents:
      - `naas_abi.agents.EntitytoSPARQLAgent.create_agent()`
      - `naas_abi.agents.KnowledgeGraphBuilderAgent.create_agent()`
- `class OntologyEngineerAgent(Agent)`
  - Subclass of `Agent` with no additional methods/attributes (placeholder for the configured agent type).

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.Agent`:
  - `Agent`, `AgentConfiguration`, `AgentSharedState`
- Uses the default model provider:
  - `naas_abi.models.default.get_model`
- Composes two other agents:
  - `naas_abi.agents.EntitytoSPARQLAgent`
  - `naas_abi.agents.KnowledgeGraphBuilderAgent`
- `SYSTEM_PROMPT` defines operating guidelines, including:
  - Educational BFO Q&A behavior.
  - Delegation to `Entity_to_SPARQL` for mapping text to SPARQL.
  - Delegation to `Knowledge_Graph_Builder` for triplestore insertion (with a confirmation step described in the prompt).

## Usage
```python
from naas_abi.agents.OntologyEngineerAgent import create_agent

agent = create_agent()
print(type(agent).__name__)  # OntologyEngineerAgent
```

With explicit configuration/state:
```python
from naas_abi.agents.OntologyEngineerAgent import create_agent, SYSTEM_PROMPT
from naas_abi_core.services.agent.Agent import AgentConfiguration, AgentSharedState

cfg = AgentConfiguration(system_prompt=SYSTEM_PROMPT)
state = AgentSharedState()
agent = create_agent(agent_shared_state=state, agent_configuration=cfg)
```

## Caveats
- The `OntologyEngineerAgent` class itself adds no behavior; all behavior is inherited from `Agent` and driven by configuration (`SYSTEM_PROMPT`) and attached sub-agents.
- No tools are registered (`tools = []`); only sub-agents are attached.
