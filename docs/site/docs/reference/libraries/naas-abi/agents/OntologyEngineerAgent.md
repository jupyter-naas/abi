# OntologyEngineerAgent

## What it is
An `Agent` implementation configured to act as a BFO (Basic Formal Ontology) expert and ontology engineering specialist, with a system prompt that guides:
- answering educational BFO questions, and
- delegating text-to-ontology mapping and triplestore operations to subordinate agents.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Optional[Agent]`
  - Factory that builds and returns an `OntologyEngineerAgent` preconfigured with:
    - default chat model (`naas_abi.models.default.get_model()`),
    - `AgentConfiguration(system_prompt=SYSTEM_PROMPT)` if none provided,
    - `AgentSharedState()` if none provided,
    - sub-agents:
      - `EntitytoSPARQLAgent.create_agent()`
      - `KnowledgeGraphBuilderAgent.create_agent()`

- `class OntologyEngineerAgent(Agent)`
  - Concrete agent type; no additional methods beyond the base `Agent` (inherits behavior).

## Configuration/Dependencies
- Depends on core agent types:
  - `naas_abi_core.services.agent.Agent.Agent`
  - `AgentConfiguration`, `AgentSharedState`
- Loads model via:
  - `naas_abi.models.default.get_model()`
- Composes two other agents:
  - `naas_abi.agents.EntitytoSPARQLAgent.create_agent`
  - `naas_abi.agents.KnowledgeGraphBuilderAgent.create_agent`
- Key constants:
  - `NAME = "Ontology_Engineer"`
  - `DESCRIPTION = "A agent that helps users understand BFO Ontology and transform text into ontologies."`
  - `SYSTEM_PROMPT` (defines operating guidelines and constraints)

## Usage
```python
from naas_abi.agents.OntologyEngineerAgent import create_agent

agent = create_agent()
# The returned object is an OntologyEngineerAgent (subclass of Agent),
# configured with the SYSTEM_PROMPT and two sub-agents.
```

## Caveats
- The module’s behavior is primarily defined by `SYSTEM_PROMPT`; the `OntologyEngineerAgent` class itself does not add custom logic (it is `pass`).
- `create_agent()` instantiates sub-agents immediately (`entity_to_sparql_agent()` and `knowledge_graph_builder_agent()`), which may have side effects depending on those implementations.
