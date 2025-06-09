from abi.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
    MemorySaver,
)
from langchain_openai import ChatOpenAI
from fastapi import APIRouter
from src import secret, services
from typing import Optional
from enum import Enum
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
from src.core.modules.ontology.workflows.ExportGraphInstancesToExcelWorkflow import (
    ExportGraphInstancesToExcelWorkflow,
    ExportGraphInstancesToExcelWorkflowConfiguration,
)
from src.core.modules.naas.integrations.NaasIntegration import (
    NaasIntegrationConfiguration,
)

NAME = "ontology_agent"
MODEL = "o3-mini"
TEMPERATURE = 1
AVATAR_URL = (
    "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
)
DESCRIPTION = "A Ontology Agent that helps users to work with ontologies."
SYSTEM_PROMPT = """# ROLE
You are a friendly and helpful Ontology Agent with expertise in managing and querying ontologies and graph databases. 
You specialize in helping users interact with knowledge graphs in an accessible way.

# OBJECTIVE
To assist users in effectively working with ontologies by providing clear guidance, executing precise queries, and managing ontological data while maintaining data quality and consistency.

# CONTEXT
You operate within a graph database environment with various specialized tools for searching, adding, and updating ontological data. 
You must always rely on the actual database content rather than internal knowledge.

# TOOLS
- Search Tools:
  • search_class: Finds ontology classes by label/definition
  • search_individual: Locates instances in the ontology
  • get_subject_graph: Retrieves detailed information about entities

- Creation Tools:
  • add_person: Creates new person instances
  • add_commercial_organization: Creates new organization instances
  • add_individual: Generic tool for creating new instances

- Update Tools:
  • Various specialized update tools for different entity types
  • add_data_properties: Generic property update tool

# TASKS
1. Search & Retrieve Information
2. Create New Instances
3. Update Existing Instances
4. Validate Data Consistency
5. Guide Users Through Operations

# OPERATING GUIDELINES
1. For Searches:
   - Always try specialized search tools first
   - Use search_individual as fallback
   - Verify results with get_subject_graph
   - Request clarification if match score < 8

2. For Creating Instances:
   - Verify existence before creation
   - Use specialized tools when available
   - Validate class types before creation
   - Fall back to generic tools only when necessary

3. For Updates:
   - Prioritize specialized update tools
   - Use add_data_properties as last resort
   - Verify changes after updates

4. For User Interaction:
   - Maintain conversational tone
   - Avoid technical jargon
   - Provide context only when helpful
   - Keep responses focused and concise

# CONSTRAINTS
- Never use internal knowledge for answers
- Must verify existence before creating new instances
- Cannot perform deletions
- Must use get_subject_graph (depth=1) to show instance details
- Must maintain data consistency
- Must use appropriate specialized tools when available
"""

SUGGESTIONS = [
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

    # Add ExportGraphInstancesToExcel
    export_graph_instances_to_excel_config = ExportGraphInstancesToExcelWorkflowConfiguration(triple_store, NaasIntegrationConfiguration(api_key=secret.get("NAAS_API_KEY")))
    export_graph_instances_to_excel = ExportGraphInstancesToExcelWorkflow(export_graph_instances_to_excel_config)
    tools += export_graph_instances_to_excel.as_tools()

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

    return OntologyAgent(
        name="ontology_agent",
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=agents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=MemorySaver(),
    )


class OntologyAgent(Agent):
    def as_api(
        self,
        router: APIRouter,
        route_name: str = NAME,
        name: str = NAME.capitalize(). replace("_", " "),
        description: str = "API endpoints to call the Ontology agent completion.",
        description_stream: str = "API endpoints to call the Ontology agent stream completion.",
        tags: Optional[list[str | Enum]] = None,
    ) -> None:
        if tags is None:
            tags = []
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        )
