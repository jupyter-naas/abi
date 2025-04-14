from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from langchain_openai import ChatOpenAI
from fastapi import APIRouter
from src import secret, services
# Foundational
from src.core.modules.ontology.pipelines.AddIndividualPipeline import AddIndividualPipeline, AddIndividualPipelineConfiguration
from src.core.modules.ontology.workflows.SearchClassWorkflow import SearchClassWorkflow, SearchClassConfigurationWorkflow
from src.core.modules.ontology.workflows.SearchIndividualWorkflow import SearchIndividualWorkflow, SearchIndividualConfigurationWorkflow
from src.core.modules.ontology.workflows.GetIndividualsFromClassWorkflow import GetIndividualsFromClassWorkflow, GetIndividualsFromClassConfigurationWorkflow
# Specialized
from src.core.modules.ontology.pipelines.AddCommercialOrganizationPipeline import AddCommercialOrganizationPipeline, AddCommercialOrganizationPipelineConfiguration
from src.core.modules.ontology.pipelines.AddLinkedInPagePipeline import AddLinkedInPagePipeline, AddLinkedInPagePipelineConfiguration
from src.core.modules.ontology.pipelines.AddPersonPipeline import AddPersonPipeline, AddPersonPipelineConfiguration
from src.core.modules.ontology.pipelines.AddSkillPipeline import AddSkillPipeline, AddSkillPipelineConfiguration
from src.core.modules.ontology.pipelines.AddWebsitePipeline import AddWebsitePipeline, AddWebsitePipelineConfiguration
from src.core.modules.ontology.pipelines.AddLegalNamePipeline import AddLegalNamePipeline, AddLegalNamePipelineConfiguration
from src.core.modules.ontology.pipelines.AddTickerPipeline import AddTickerPipeline, AddTickerPipelineConfiguration

from src.core.modules.ontology.workflows.SearchPersonWorkflow import SearchPersonWorkflow, SearchPersonConfigurationWorkflow
from src.core.modules.ontology.workflows.SearchSkillWorkflow import SearchSkillWorkflow, SearchSkillConfigurationWorkflow
from src.core.modules.ontology.workflows.SearchCommercialOrganizationWorkflow import SearchCommercialOrganizationWorkflow, SearchCommercialOrganizationConfigurationWorkflow
from src.core.modules.ontology.workflows.SearchWebsitePipeline import SearchWebsiteWorkflow, SearchWebsiteConfigurationWorkflow
from src.core.modules.ontology.workflows.SearchLinkedInPagePipeline import SearchLinkedInPageWorkflow, SearchLinkedInPageConfigurationWorkflow
from src.core.modules.ontology.workflows.SearchTickerPipeline import SearchTickerWorkflow, SearchTickerConfigurationWorkflow
from src.core.modules.ontology.workflows.SearchLegalNamePipeline import SearchLegalNameWorkflow, SearchLegalNameConfigurationWorkflow

from src.core.modules.ontology.workflows.GetPersonsAssociatedwithSkillsWorkflow import GetPersonsAssociatedwithSkillsWorkflow, GetPersonsAssociatedwithSkillsConfigurationWorkflow
from src.core.modules.ontology.workflows.GetSkillsAssociatedwithPersonsWorkflow import GetSkillsAssociatedwithPersonsWorkflow, GetSkillsAssociatedwithPersonsConfigurationWorkflow

NAME = "Ontology Agent"
MODEL = "o3-mini"
TEMPERATURE = 1
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
DESCRIPTION = "A Ontology Agent that helps users to work with ontologies."
SYSTEM_PROMPT = f"""You are a Ontology Agent that helps users to work with ontologies.
You have the possibility to add or retrieve data from triple store with your tools.
You must ALWAYS identify the best tool to use to answer the user's question.

Specific rules: Add Individual
--------------------------------
Before adding/updating an new individual/instance to the ontology always try to find if it does not already exist in the ontology.
To do so follow these steps:
1. Search the individual:
    Search if the individual already exists in the ontology using corresponding workflows. For example, if the user request to add a person like "Add Florent Ravenel", you can use the `ontology_search_person` tool.
    If no workflows exists:
        - Search the class that could be used to add the individual using the `ontology_search_class` tool. If you find a class with a score >= 9 use it. If not ask user for validation.
        - Search if the individual already exists using the `ontology_search_individual` tool.
2. Add or update the individual:
    If the individual doesn't exist, add it to the ontology, if it exists update it by passing the individual URI (parameter: individual_uri).
    All parameters that need a URI (ends with "_uri" or "_uris") must be created as individual in the ontology using this same process. A valid URI must start with the namespace abi: "http://ontology.naas.ai/abi/".
    Try to use existing pipelines. For example, if the user request to add a person like "Add Florent Ravenel", you can use the `ontology_add_person` tool.
    If you can't find a corresponding pipeline, use the `ontology_add_individual` tool with the class found in step 1.

Always provide all the context (tool response, draft, etc.) to the user in your final response.
"""

SUGGESTIONS = [
    {
        "label": "Learn About Ontology",
        "value": "What's the ontology about?"
    },
    {
        "label": "Ontology Object Explorer",
        "value": "What is a {{Github Issue}} in the ontology?"
    },
    {
        "label": "Add Data To Ontology",
        "value": "Add the following data in ontology: {{Data}}"
    }
]

def create_agent(
    agent_shared_state: AgentSharedState = None, 
    agent_configuration: AgentConfiguration = None
) -> Agent:
    # Init
    tools = []
    agents = []
    triple_store = services.triple_store_service

    # Set model
    model = ChatOpenAI(
        model=MODEL,
        temperature=TEMPERATURE, 
        api_key=secret.get('OPENAI_API_KEY')
    )
    # Init store
    triple_store = services.triple_store_service

    # Add Foundational Tools
    add_individual_pipeline_configuration = AddIndividualPipelineConfiguration(triple_store)
    add_individual_pipeline = AddIndividualPipeline(add_individual_pipeline_configuration)
    tools += add_individual_pipeline.as_tools()

    search_class_workflow = SearchClassWorkflow(SearchClassConfigurationWorkflow(triple_store))
    tools += search_class_workflow.as_tools()

    search_individual_workflow = SearchIndividualWorkflow(SearchIndividualConfigurationWorkflow(triple_store))
    tools += search_individual_workflow.as_tools()

    get_individuals_from_class_workflow = GetIndividualsFromClassWorkflow(GetIndividualsFromClassConfigurationWorkflow(triple_store))
    tools += get_individuals_from_class_workflow.as_tools()

    # Specialized Tools
    add_person_pipeline_configuration = AddPersonPipelineConfiguration(triple_store, add_individual_pipeline_configuration)
    add_person_pipeline = AddPersonPipeline(add_person_pipeline_configuration)
    tools += add_person_pipeline.as_tools()

    # search_person_workflow = SearchPersonWorkflow(SearchPersonConfigurationWorkflow(triple_store))
    # tools += search_person_workflow.as_tools()

    add_skill_pipeline_configuration = AddSkillPipelineConfiguration(triple_store, add_individual_pipeline_configuration)
    add_skill_pipeline = AddSkillPipeline(add_skill_pipeline_configuration)
    tools += add_skill_pipeline.as_tools()

    search_skill_workflow = SearchSkillWorkflow(SearchSkillConfigurationWorkflow(triple_store))
    tools += search_skill_workflow.as_tools()

    add_commercial_organization_pipeline_configuration = AddCommercialOrganizationPipelineConfiguration(triple_store, add_individual_pipeline_configuration)
    add_commercial_organization_pipeline = AddCommercialOrganizationPipeline(add_commercial_organization_pipeline_configuration)
    tools += add_commercial_organization_pipeline.as_tools()

    search_commercial_organization_workflow = SearchCommercialOrganizationWorkflow(SearchCommercialOrganizationConfigurationWorkflow(triple_store))
    tools += search_commercial_organization_workflow.as_tools()

    add_linkedin_page_pipeline_configuration = AddLinkedInPagePipelineConfiguration(triple_store, add_individual_pipeline_configuration)
    add_linkedin_page_pipeline = AddLinkedInPagePipeline(add_linkedin_page_pipeline_configuration)
    tools += add_linkedin_page_pipeline.as_tools()

    search_linkedin_page_workflow = SearchLinkedInPageWorkflow(SearchLinkedInPageConfigurationWorkflow(triple_store))
    tools += search_linkedin_page_workflow.as_tools()

    add_website_pipeline_configuration = AddWebsitePipelineConfiguration(triple_store, add_individual_pipeline_configuration)
    add_website_pipeline = AddWebsitePipeline(add_website_pipeline_configuration)
    tools += add_website_pipeline.as_tools()

    search_website_workflow = SearchWebsiteWorkflow(SearchWebsiteConfigurationWorkflow(triple_store))
    tools += search_website_workflow.as_tools()

    add_legal_name_pipeline_configuration = AddLegalNamePipelineConfiguration(triple_store, add_individual_pipeline_configuration)
    add_legal_name_pipeline = AddLegalNamePipeline(add_legal_name_pipeline_configuration)
    tools += add_legal_name_pipeline.as_tools()

    add_ticker_pipeline_configuration = AddTickerPipelineConfiguration(triple_store, add_individual_pipeline_configuration)
    add_ticker_pipeline = AddTickerPipeline(add_ticker_pipeline_configuration)
    tools += add_ticker_pipeline.as_tools()

    search_ticker_workflow = SearchTickerWorkflow(SearchTickerConfigurationWorkflow(triple_store))
    tools += search_ticker_workflow.as_tools()

    add_legal_name_pipeline_configuration = AddLegalNamePipelineConfiguration(triple_store, add_individual_pipeline_configuration)
    add_legal_name_pipeline = AddLegalNamePipeline(add_legal_name_pipeline_configuration)
    tools += add_legal_name_pipeline.as_tools()

    search_legal_name_workflow = SearchLegalNameWorkflow(SearchLegalNameConfigurationWorkflow(triple_store))
    tools += search_legal_name_workflow.as_tools()
    

    get_persons_associated_with_skills_workflow = GetPersonsAssociatedwithSkillsWorkflow(GetPersonsAssociatedwithSkillsConfigurationWorkflow(triple_store))
    tools += get_persons_associated_with_skills_workflow.as_tools()

    get_skills_associated_with_persons_workflow = GetSkillsAssociatedwithPersonsWorkflow(GetSkillsAssociatedwithPersonsConfigurationWorkflow(triple_store))
    tools += get_skills_associated_with_persons_workflow.as_tools()

    # Use provided configuration or create default one
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)
    
    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()
    
    # Override tools
    from src.core.modules.intentmapping import get_tools
    tools.extend(get_tools())
    
    return OntologyAgent(
        name="ontology_agent", 
        description=DESCRIPTION,
        chat_model=model, 
        tools=tools, 
        agents=agents,
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    )

class OntologyAgent(Agent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = "ontology", 
        name: str = "Ontology Agent", 
        description: str = "API endpoints to call the Ontology agent completion.", 
        description_stream: str = "API endpoints to call the Ontology agent stream completion.",
        tags: list[str] = []
    ):
        return super().as_api(router, route_name, name, description, description_stream, tags)