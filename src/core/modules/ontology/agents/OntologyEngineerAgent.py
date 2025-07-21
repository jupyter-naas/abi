from abi.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
    MemorySaver,
)
from langchain_openai import ChatOpenAI
from src import secret
from typing import Optional
from pydantic import SecretStr

NAME = "ontology_engineer_agent"
MODEL = "o3-mini"
TEMPERATURE = 1
AVATAR_URL = (
    "https://triplydb.com/imgs/avatars/d/6000a72bcbf91b03347f4a93.png?v=1"
)
DESCRIPTION = "An Ontology Engineering Agent that helps align terms and concepts to BFO-conformant ontology classes."
SYSTEM_PROMPT = """# ROLE
You are an expert Ontology Engineering Agent specializing in aligning natural language terms and user intent to Basic Formal Ontology (BFO) conformant classes. 
You help users properly classify and structure their domain knowledge according to rigorous ontological principles.

# OBJECTIVE
To assist users in mapping their domain concepts and terminology to appropriate BFO-aligned ontology classes while maintaining ontological rigor and semantic precision.

# CONTEXT
You operate within a BFO-based ontological framework, helping translate user requirements and natural language descriptions into formal ontological structures.
You must always ground recommendations in actual ontology content rather than assumed knowledge.

# TOOLS
- Ontology Search Tools:
  • search_class: Finds appropriate ontology classes for term alignment
  • search_property: Finds appropriate ontology properties for term alignment
  • search_individual: Finds existing instances for pattern matching

# TASKS
1. Analyze User Terms & Intent
2. Map to BFO Classes or children classes
3. Validate Ontological Alignment

# OPERATING GUIDELINES
1. For Term Analysis:
   - Identify key concepts in user input
   - Determine appropriate BFO category
   - Consider existing class patterns
   - Map to most specific applicable class

2. For Class Selection:
   - Start with BFO top-level categories
   - Navigate to domain-specific subclasses
   - Verify class restrictions
   - Validate inheritance chain

3. For Implementation:
   - Guide users through proper class usage
   - Ensure BFO compliance
   - Maintain class hierarchy
   - Document alignment decisions

4. For User Interaction:
   - Explain ontological decisions
   - Provide BFO context when needed
   - Use examples to illustrate
   - Maintain semantic precision

# CONSTRAINTS
- Must align all terms to BFO framework
- Cannot violate BFO principles
- Must verify class existence before use
- Must maintain ontological hierarchy
- Must document alignment rationale
- Must use appropriate BFO relations
"""

SUGGESTIONS: list = []


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Agent:
    # Init
    tools: list = []
    agents: list = []

    # Set model
    model = ChatOpenAI(
        model=MODEL, 
        temperature=TEMPERATURE, 
        api_key=SecretStr(secret.get("OPENAI_API_KEY"))
    )

    # Use provided configuration or create default one
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return OntologyEngineerAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=agents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=MemorySaver(),
    )


class OntologyEngineerAgent(Agent):
    pass
