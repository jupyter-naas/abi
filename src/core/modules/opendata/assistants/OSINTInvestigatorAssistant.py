from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret, config, services
from langchain_openai import ChatOpenAI
from src.core.modules.common.integrations import LinkedInIntegration, GoogleSearchIntegration, NewsAPIIntegration, PerplexityIntegration, OpenAIIntegration
from src.core.modules.common.integrations.LinkedInIntegration import LinkedInIntegrationConfiguration
from src.core.modules.common.integrations.NaasIntegration import NaasIntegrationConfiguration
from src.core.modules.common.integrations.PerplexityIntegration import PerplexityIntegrationConfiguration
from src.core.modules.common.integrations.GoogleSearchIntegration import GoogleSearchIntegrationConfiguration
from src.core.modules.common.integrations.NewsAPIIntegration import NewsAPIIntegrationConfiguration
from src.core.modules.common.integrations.OpenAIIntegration import OpenAIIntegrationConfiguration
from src.core.modules.common.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT
from src.core.modules.common.workflows.abi.CreateOntologyYAML import CreateOntologyYAMLConfiguration

from ..workflows.PerplexityGetOrganizationWorkflows import PerplexityOrganizationWorkflowsConfiguration
from ..pipelines.PerplexityOrganizationAnalysisPipeline import PerplexityOrganizationAnalysisPipeline, PerplexityOrganizationAnalysisPipelineConfiguration
from fastapi import APIRouter

NAME = "OSINT Investigator Assistant"
SLUG = "osint-investigator-assistant"
DESCRIPTION = "Gather open-source intelligence, including LinkedIn profile analysis, Perplexity AI research, Google Search results, NewsAPI for current events, and OpenAI's capabilities. It can also leverage specialized pipelines for organization analysis and ontology management, enabling comprehensive data collection and structured information storage."
MODEL = "o3-mini"
TEMPERATURE = 1
AVATAR_URL = "https://workspace-dev-ugc-public-access.s3.us-west-2.amazonaws.com/5d4797db-0ac2-418b-9b81-5b1c6e6cfc3a/images/0f05ffdfc6e44b70b078830a2f3810a2"
SYSTEM_PROMPT = f"""You are the OSINT (Open Source Intelligence) Investigator Assistant. 
Your responsibility is to gather, analyze, and report on publicly available information from open data sources, such as social media, government records, and news platforms. 
You track key data on competitors, industry trends, and public sentiment to support decision-making and strategic initiatives.

You have access to powerful tools for gathering open-source intelligence, including LinkedIn profile analysis, Perplexity AI research, Google Search results, NewsAPI for current events, and OpenAI's capabilities. You can also leverage specialized pipelines for organization analysis and ontology management, enabling comprehensive data collection and structured information storage.

RESPONSIBILITIES
-----------------
{RESPONSIBILITIES_PROMPT}
"""

def create_osint_investigator_agent(
    agent_shared_state: AgentSharedState = None, 
    agent_configuration: AgentConfiguration = None
) -> Agent:
    model = ChatOpenAI(
        model=MODEL, 
        temperature=TEMPERATURE, 
        api_key=secret.get('OPENAI_API_KEY')
    )
    tools = []

    # LinkedinIntegration
    li_at = secret.get('li_at')
    JSESSIONID = secret.get('JSESSIONID')
    if li_at and JSESSIONID:
        linkedin_integration_config = LinkedInIntegrationConfiguration(li_at=li_at, JSESSIONID=JSESSIONID)
        tools += LinkedInIntegration.as_tools(linkedin_integration_config)

    # PerplexityIntegration
    perplexity_api_key = secret.get('PERPLEXITY_API_KEY')
    if perplexity_api_key:
        perplexity_integration_config = PerplexityIntegrationConfiguration(api_key=perplexity_api_key)
        tools += PerplexityIntegration.as_tools(perplexity_integration_config)

    # NaasIntegration
    naas_api_key = secret.get('NAAS_API_KEY')
    if naas_api_key:
        naas_integration_config = NaasIntegrationConfiguration(api_key=naas_api_key)

    # NewsAPIIntegration
    newsapi_api_key = secret.get('NEWSAPI_API_KEY')
    if newsapi_api_key:
        newsapi_integration_config = NewsAPIIntegrationConfiguration(api_key=newsapi_api_key)
        tools += NewsAPIIntegration.as_tools(newsapi_integration_config)

    # GoogleSearchIntegration
    google_integration_config = GoogleSearchIntegrationConfiguration()
    tools += GoogleSearchIntegration.as_tools(google_integration_config)

    # OpenAIIntegration
    openai_api_key = secret.get('OPENAI_API_KEY')
    if openai_api_key:
        openai_integration_config = OpenAIIntegrationConfiguration(api_key=openai_api_key)
        tools += OpenAIIntegration.as_tools(openai_integration_config)

    # Setup ontology store
    ontology_store = services.ontology_store_service

    # Init pipelines
    if perplexity_api_key and naas_api_key:
        # Initialize workflows configuration
        perplexity_organization_workflows_config = PerplexityOrganizationWorkflowsConfiguration(
            perplexity_integration_config=perplexity_integration_config,
        )
        create_ontology_yaml_config = CreateOntologyYAMLConfiguration(
            naas_integration_config=naas_integration_config,
            ontology_store=ontology_store
        )

        # Setup pipeline
        pipeline = PerplexityOrganizationAnalysisPipeline(PerplexityOrganizationAnalysisPipelineConfiguration(
            ontology_store=ontology_store,
            naas_integration_config=naas_integration_config,
            perplexity_organization_workflows_config=perplexity_organization_workflows_config,
            create_ontology_yaml_config=create_ontology_yaml_config,
        ))
        tools += pipeline.as_tools()
    else:
        print("No perplexity API key or naas API key or li_at or JSESSIONID")
        print(f"perplexity_api_key: {perplexity_api_key}")
        print(f"naas_api_key: {naas_api_key}")
        print(f"li_at: {li_at}")
        print(f"JSESSIONID: {JSESSIONID}")
        exit()

    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT
        )
    
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()
    
    return OSINTInvestigatorAssistant(
        name=NAME.lower().replace(" ", "_"),
        description=DESCRIPTION,
        chat_model=model, 
        tools=tools, 
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 

create_agent = create_osint_investigator_agent

class OSINTInvestigatorAssistant(Agent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = "osint_investigator", 
        name: str = "OSINT Investigator Assistant", 
        description: str = "API endpoints to call the OSINT Investigator assistant completion.", 
        description_stream: str = "API endpoints to call the OSINT Investigator assistant stream completion.",
        tags: list[str] = []
    ):
        return super().as_api(router, route_name, name, description, description_stream, tags)