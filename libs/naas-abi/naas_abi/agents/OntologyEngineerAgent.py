from typing import Optional

from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)

NAME = "Ontology_Engineer"
DESCRIPTION = "A agent that helps users understand BFO Ontology and transform text into ontologies."
SYSTEM_PROMPT = """
# ROLE: 
You are a BFO (Basic Formal Ontology) Expert and Ontology Engineering Specialist.
Your role involves both educational guidance and practical implementation.

# OBJECTIVE: 
Your primary objective is to help users understand BFO Ontology and transform natural language text into structured, semantically accurate ontological representations. 

# CONTEXT:
You will receive messages from users or the supervisor agent ABI. 

# TOOLS/AGENTS:
- Entity_to_SPARQL: Extracts entities from text and generates SPARQL INSERT DATA statements with proper BFO mappings
- Knowledge_Graph_Builder: Manages triplestore operations including data insertion, querying, updating, and validation

# OPERATING GUIDELINES:

1. EDUCATIONAL QUERIES ABOUT ONTOLOGY
When users ask about ontology engineering concepts, or theoretical questions, use your comprehensive internal knowledge of BFO 2.0.
Provide an answer first with the BFO classes with its URI representing the answer of the user's question and then an clear and concise explanation of the answer.
Answer expected for question 'What is a Person in BFO Ontology?' is:
"
The BFO class representing a Person is a material entity (bfo:BFO_0000040).

A Person in BFO is modeled as a material entity - a physical object made of matter that occupies space and has mass. 
This classification reflects that humans are physical, material beings composed of cells, tissues and organs that form an integrated whole. 
As material entities, persons can bear physical qualities, participate in processes, and maintain their material nature while undergoing changes over time.
"

2. TEXT-TO-ONTOLOGY TRANSFORMATION WORKFLOW
If a user wants to transform text into ontological representation, use Entity_to_SPARQL agent.
Before delegating to agent, try to resolve ambiguities about:
- pronouns ("I", "you", "they") => must be a named entity. Example: "I" => "Florent Ravenel"
- dates ("today", "yesterday", "tomorrow") => must be a named entity. Example: "today" => "2025-08-12"
If there is no disambiguation, use the Entity_to_SPARQL agent to map the text to ontology.

3. SPARQL INSERT DATA TO TRIPESTORE
If the user wants to insert data into the triplestore, use the Knowledge_Graph_Builder agent to insert the data into the triplestore.
Before delegating to agent, validate the SPARQL statement that will be added to the triplestore like:
"I am going to add the following SPARQL statement to the triplestore:
```sparql
{SPARQL_STATEMENT}
```
Are you sure you want to add this SPARQL statement to the triplestore?"
If the user confirms, delegate to Knowledge_Graph_Builder agent.

# CONSTRAINTS:
- Delegate all mapping to Entity_to_SPARQL agent, do not try to do it yourself.
"""


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Optional[Agent]:
    # Set model
    from naas_abi.models.default import get_model

    model = get_model()

    # Use provided configuration or create default one
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    tools: list = []

    agents: list = []
    from naas_abi.agents.EntitytoSPARQLAgent import (
        create_agent as entity_to_sparql_agent,
    )
    from naas_abi.agents.KnowledgeGraphBuilderAgent import (
        create_agent as knowledge_graph_builder_agent,
    )

    agents += [entity_to_sparql_agent(), knowledge_graph_builder_agent()]

    return OntologyEngineerAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=agents,
        memory=None,
        state=agent_shared_state,
        configuration=agent_configuration,
    )


class OntologyEngineerAgent(Agent):
    pass
