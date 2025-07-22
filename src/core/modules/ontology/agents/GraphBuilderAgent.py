from abi.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
    MemorySaver,
)
from langchain_openai import ChatOpenAI
from src import secret, services
from typing import Optional
from pydantic import SecretStr

# Foundational
from src.core.modules.ontology.pipelines.AddIndividualPipeline import (
    AddIndividualPipeline,
    AddIndividualPipelineConfiguration,
)
from src.core.modules.ontology.workflows.SearchIndividualWorkflow import (
    SearchIndividualWorkflow,
    SearchIndividualWorkflowConfiguration,
)
from src.core.modules.ontology.workflows.GetSubjectGraphWorkflow import (
    GetSubjectGraphWorkflow,
    GetSubjectGraphWorkflowConfiguration,
)
# Specialized
from src.core.modules.ontology.pipelines.UpdateCommercialOrganizationPipeline import (
    UpdateCommercialOrganizationPipeline,
    UpdateCommercialOrganizationPipelineConfiguration,
)
from src.core.modules.ontology.pipelines.UpdateLinkedInPagePipeline import (
    UpdateLinkedInPagePipeline,
    UpdateLinkedInPagePipelineConfiguration,
)
from src.core.modules.ontology.pipelines.UpdatePersonPipeline import (
    UpdatePersonPipeline,
    UpdatePersonPipelineConfiguration,
)
from src.core.modules.ontology.pipelines.UpdateSkillPipeline import (
    UpdateSkillPipeline,
    UpdateSkillPipelineConfiguration,
)
from src.core.modules.ontology.pipelines.UpdateWebsitePipeline import (
    UpdateWebsitePipeline,
    UpdateWebsitePipelineConfiguration,
)
from src.core.modules.ontology.pipelines.UpdateLegalNamePipeline import (
    UpdateLegalNamePipeline,
    UpdateLegalNamePipelineConfiguration,
)
from src.core.modules.ontology.pipelines.UpdateTickerPipeline import (
    UpdateTickerPipeline,
    UpdateTickerPipelineConfiguration,
)

NAME = "graph_builder_agent"
MODEL = "o3-mini"
TEMPERATURE = 1
AVATAR_URL = (
    "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f3/Rdf_logo.svg/1200px-Rdf_logo.svg.png"
)
DESCRIPTION = "A Graph Builder Agent that assembles entities and relationships into RDF triples for knowledge graph construction."
SYSTEM_PROMPT = """# ROLE
You are a friendly and helpful Graph Builder Agent with expertise in assembling entities and relationships into RDF triples. 
You specialize in constructing knowledge graphs by identifying, creating, and connecting entities through precise relationships.

# OBJECTIVE
To assist users in effectively building knowledge graphs by assembling entities and their relationships into RDF triples, ensuring data quality, consistency, and proper graph structure.

# CONTEXT
You operate within a graph database environment where you construct knowledge representations by creating entities, defining their properties, and establishing relationships between them. You transform raw information into structured RDF triples that form a comprehensive knowledge graph.

# TOOLS
- Discovery Tools:
  • search_class: Identifies existing ontology classes for proper entity typing
  • search_individual: Locates existing entities to avoid duplication and establish connections
  • get_subject_graph: Retrieves detailed entity information and relationship patterns

- Entity Creation Tools:
  • add_person: Assembles person entities with their associated triples
  • add_commercial_organization: Constructs organization entities and their relationships
  • add_individual: Generic entity builder for various instance types

- Relationship Assembly Tools:
  • Various specialized update tools for different entity relationship patterns
  • add_data_properties: Generic property and relationship builder

# TASKS
1. Identify and Extract Entities from Information
2. Determine Appropriate Entity Types and Classes
3. Assemble Entities into Structured RDF Triples
4. Establish Relationships Between Entities
5. Validate Graph Structure and Consistency
6. Guide Users Through Graph Construction Process

# OPERATING GUIDELINES
1. For Entity Discovery:
   - Search existing graph structure before creating new entities
   - Use specialized search tools to understand entity context
   - Verify entity relationships with get_subject_graph
   - Request clarification for ambiguous entities (match score < 8)

2. For Entity Assembly:
   - Verify entity uniqueness before creation
   - Use specialized creation tools for optimal triple structure
   - Validate entity types against ontology classes
   - Ensure proper RDF triple formation

3. For Relationship Building:
   - Prioritize specialized relationship assembly tools
   - Use generic property tools only when specific tools unavailable
   - Verify relationship consistency after assembly
   - Maintain graph integrity and coherence

4. For User Interaction:
   - Maintain conversational and helpful tone
   - Explain graph building concepts clearly
   - Focus on practical graph construction guidance
   - Keep responses actionable and concise

# CONSTRAINTS
- Must verify existing graph structure before adding new triples
- Cannot delete entities or relationships
- Must use get_subject_graph (depth=1) to display entity details and connections
- Must maintain RDF triple consistency and validity
- Must use appropriate specialized tools for optimal graph assembly
- Always build upon existing graph structure rather than replacing it
"""

SUGGESTIONS: list = [
    {"label": "Learn About Ontology", "value": "What's the ontology about?"},
    {
        "label": "Ontology Object Explorer",
        "value": "What is a {{Github Issue}} in the ontology?",
    },
    {
        "label": "Add Data To Ontology",
        "value": "Add the following data in ontology: {{Data}}",
    },
]


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Agent:
    # Init
    tools: list = []
    agents: list = []
    triple_store = services.triple_store_service

    # Set model
    model = ChatOpenAI(
        model=MODEL, 
        temperature=TEMPERATURE, 
        api_key=SecretStr(secret.get("OPENAI_API_KEY"))
    )
    # Init store
    triple_store = services.triple_store_service

    # Add Foundational Tools
    ## Initialize search workflow first since add pipeline depends on it
    search_config = SearchIndividualWorkflowConfiguration(triple_store)
    search_workflow = SearchIndividualWorkflow(search_config)
    tools += search_workflow.as_tools()

    ## Initialize add pipeline with search workflow config
    add_config = AddIndividualPipelineConfiguration(triple_store, search_config)
    add_pipeline = AddIndividualPipeline(add_config)
    tools += add_pipeline.as_tools()

    # Add GetSubjectGraphWorkflow
    get_subject_graph_config = GetSubjectGraphWorkflowConfiguration()
    get_subject_graph_workflow = GetSubjectGraphWorkflow(get_subject_graph_config)
    tools += get_subject_graph_workflow.as_tools()

    # Specialized Tools
    ## Initialize specialized pipelines
    specialized_pipelines = [
        (UpdatePersonPipeline, UpdatePersonPipelineConfiguration),
        (UpdateSkillPipeline, UpdateSkillPipelineConfiguration),
        (UpdateCommercialOrganizationPipeline, UpdateCommercialOrganizationPipelineConfiguration),
        (UpdateLinkedInPagePipeline, UpdateLinkedInPagePipelineConfiguration),
        (UpdateWebsitePipeline, UpdateWebsitePipelineConfiguration), 
        (UpdateLegalNamePipeline, UpdateLegalNamePipelineConfiguration),
        (UpdateTickerPipeline, UpdateTickerPipelineConfiguration)
    ]

    for Pipeline, Configuration in specialized_pipelines:
        tools += Pipeline(Configuration(triple_store)).as_tools()

    # Override tools
    from src.core.modules.intentmapping import get_tools
    tools.extend(get_tools())

    # Use provided configuration or create default one
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return GraphBuilderAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=agents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=MemorySaver(),
    )


class GraphBuilderAgent(Agent):
    pass