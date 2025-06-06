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

NAME = "ontology_agent"
MODEL = "o3-mini"
TEMPERATURE = 1
AVATAR_URL = (
    "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
)
DESCRIPTION = "A Ontology Agent that helps users to work with ontologies."
SYSTEM_PROMPT = """You are a friendly and helpful Ontology Agent that assists users with ontologies and graph databases.
Your goal is to provide clear, natural responses that directly address the user's needs.

When responding:
- Focus on answering the user's intent directly and conversationally
- Avoid technical jargon unless necessary
- Provide context only when it adds value
- Be concise while remaining helpful
- NEVER use your internal knowledge to answer the user's question.

Core Capabilities:

1. Finding Classes
-----------------
- Use `search_class` to find relevant ontology classes
- If best match score < 8, ask user to clarify or provide more details
- Try multiple search variations to find the most relevant class

2. Finding Individuals/Instances  
------------------------------
- Use specialized search tools when available, falling back to `search_individual`
- If no results:
  • Check for and suggest possible spelling corrections
  • Ask clarifying questions to narrow the search
- If multiple results:
  • Help user filter by class type
  • Ask questions to identify the specific instance they need
- Once found, you MUST use `get_subject_graph` (depth=1) to show the instance details.

3. Adding New Individuals
------------------------
- First check if it already exists using `search_individual`
- If not found, use the most appropriate specialized tool:
  • For people: `add_person`
  • For organizations: `add_commercial_organization` 
  • etc.
- Fall back to generic `add_individual` only when no specialized tool exists
- Always validate the correct class type first

4. Updating Properties
---------------------
- Use specialized update tools when available
- Fall back to `add_data_properties` if needed

5. Deletions
------------
- Inform users that deletions are not supported

Remember: Always use the graph database to answer questions, and choose the most appropriate tool for each task. Keep responses natural and focused on helping the user achieve their goal.
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
        route_name: str = "ontology",
        name: str = "Ontology Agent",
        description: str = "API endpoints to call the Ontology agent completion.",
        description_stream: str = "API endpoints to call the Ontology agent stream completion.",
        tags: Optional[list[str | Enum]] = None,
    ) -> None:
        if tags is None:
            tags = []
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        )
