from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret, services
from fastapi import APIRouter
from src.core.assistants.foundation.SupportAssistant import create_support_agent
from src.core.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.core.integrations import PerplexityIntegration
from src.core.integrations.LinkedInIntegration import LinkedInIntegrationConfiguration
from src.core.integrations.NaasIntegration import NaasIntegration, NaasIntegrationConfiguration
from src.core.integrations.PerplexityIntegration import PerplexityIntegrationConfiguration

NAME = "Open Data Assistant"
DESCRIPTION = "Leverages external APIs and AI tools to access opensource data sources and indicators."
MODEL = "o3-mini"
TEMPERATURE = 1
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/open_data_intelligence.png"
SYSTEM_PROMPT = f"""You are a data intelligence expert who helps users find and analyze information from various external sources.
Your primary goal is to guide users in accessing news, financial data, extra-financial data, and alternative data through available tools and agents.
If users provide insufficient information, proactively ask clarifying questions.
Draw from your knowledge when no specific agent applies.

AGENTS
------
[AGENTS]

RESPONSIBILITIES
-----------------
{RESPONSIBILITIES_PROMPT}
"""
SUGGESTIONS = [
    {
        "label": "Feature Request",
        "value": "As a user, I would like to: [Feature Request]"
    },
    {
        "label": "Report Bug",
        "value": "Report a bug on: [Bug Description]"
    }
]

def create_open_data_agent(
    agent_shared_state: AgentSharedState = None, 
    agent_configuration: AgentConfiguration = None
) -> Agent:
    # Init
    tools = []
    agents = []

    # Set model
    model = ChatOpenAI(
        model=MODEL, 
        temperature=TEMPERATURE, 
        api_key=secret.get('OPENAI_API_KEY')
    ) 

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            on_tool_usage=lambda message: print_tool_usage(message.tool_calls[0]['name']),
            on_tool_response=lambda message: print_tool_response(f'\n{message.content}'),
            system_prompt=SYSTEM_PROMPT
        )
    
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id=0)

    # Init secrets
    li_at = None
    JSESSIONID = None
    naas_api_key = None
    perplexity_api_key = None

    # Setup ontology store
    ontology_store = services.ontology_store_service

    # NaasIntegration Configuration
    naas_api_key = secret.get('NAAS_API_KEY')
    if naas_api_key:
        naas_integration_config = NaasIntegrationConfiguration(api_key=naas_api_key)
        li_at = NaasIntegration(NaasIntegrationConfiguration(api_key=naas_api_key)).get_secret('li_at').get('secret').get('value')
        JSESSIONID = NaasIntegration(NaasIntegrationConfiguration(api_key=naas_api_key)).get_secret('JSESSIONID').get('secret').get('value')

    # LinkedinIntegration Configuration
    if li_at and JSESSIONID:
        linkedin_integration_config = LinkedInIntegrationConfiguration(li_at=li_at, JSESSIONID=JSESSIONID)

    # PerplexityIntegration Configuration + Integration
    perplexity_api_key = secret.get('PERPLEXITY_API_KEY')
    if perplexity_api_key:
        perplexity_integration_config = PerplexityIntegrationConfiguration(api_key=perplexity_api_key)
        tools += PerplexityIntegration.as_tools(perplexity_integration_config)
    
    # Add tools
    agents = [
        create_support_agent(AgentSharedState(thread_id=2), agent_configuration)
    ]

    # Get tools info from each assistant
    agents_info = []
    for agent in agents: 
        if agent.name != "support_agent":
            agent_info = {
                "name": agent.name,
                "description": agent.description,
                "tools": [
                    {"name": t.name, "description": t.description}
                    for t in agent.tools  # Access the private tools attribute
                ]
            }        
            agents_info.append(agent_info)

    # Transform assistants_info into formatted string
    agents_info_str = ""
    for agent in agents_info:
        agents_info_str += f"-{agent['name']}: {agent['description']}\n"
        for tool in agent['tools']:
            agents_info_str += f"   • {tool['name']}: {tool['description']}\n"
        agents_info_str += "\n"

    # Replace the {{AGENTS}} placeholder in the system prompt with the agents_info
    agent_configuration.system_prompt=SYSTEM_PROMPT.replace("[AGENTS]", agents_info_str)

    return OpenDataAssistant(
        name="open_data_agent", 
        description=DESCRIPTION,
        chat_model=model, 
        tools=tools, 
        agents=agents,
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 

class OpenDataAssistant(Agent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = "open_data", 
        name: str = NAME, 
        description: str = "API endpoints to call the Open Data assistant completion.", 
        description_stream: str = "API endpoints to call the Open Data assistant stream completion.",
        tags: list[str] = []
    ):
        return super().as_api(router, route_name, name, description, description_stream, tags)