from abi.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
    MemorySaver,
)
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
from src.core.modules.common.models.default import default_chat_model
from langchain_core.language_models.chat_models import BaseChatModel

NAME = "ontology_agent"
MODEL = "o3-mini"
TEMPERATURE = 1
AVATAR_URL = (
    "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
)
DESCRIPTION = "A Ontology Agent that helps users to work with ontologies."
SYSTEM_PROMPT = """You are a Ontology Agent that helps users to work with ontologies and triple store OR graph database.
You have the possibility to add or retrieve data from triple store with your tools.
You must ALWAYS identify the best tool to use to answer the user's question.
You must ALWAYS use your graph database to answer the user's question.
Report your answer by giving context and include URIs used only if asked by user.

Capabilities:

Search Class
------------
Use the `search_class` tool to search for a class.
From the results, if the best score is below 8, you must ask user for more information.
Use your internal knowledge to find the right class to use based on the user's request by trying multiples times the tool with different parameters.

Search Individual
-----------------
Use appropriate tool to search for an instance. If you can't find an appropriate tool, use the `search_individual` tool to search for an individual/instance.
-> If an empty list is returned, try to find the individual correcting the spelling mistakes that could have been made.
-> If you find multiples individuals, try to find the class uri to filter the search results by asking the user and using `search_class` tool.
From the results, if the best score is below 8, you must ask user for more information.
If the user wants to know everything about an individual, search the individual to get its URI and use the `get_individual_graph` tool to return its graph.

Adding an new individual / instance
-----------------------------------
1. Search individual:
    Search if the individual already exists with its label using `search_individual` tool.
    If you find multiples individuals, try to find the class uri to filter the search results by asking the user and using `search_class` tool.
    From the results, if the best score is below 8, you must ask user for more information.
2. Add individual:
    If the individual doesn't exist, add it using the appropriate tool. If you can't find an appropriate tool, use the `add_individual` tool after validating the right class to use with `search_class` tool.
    For example, if the user request to add a person like "Add Florent Ravenel", you can use the `add_person` tool.

Update an individual / instance properties
------------------------------------------
Use the appropriate tool to update the individual/instance properties.
If you can't find an appropriate tool, use the `add_data_properties` tool.

Delete an individual / instance
-------------------------------
You can't delete individual/instance.
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
