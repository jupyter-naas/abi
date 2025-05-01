from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret, services
from fastapi import APIRouter
from src.core.modules.naas.integrations.NaasIntegration import NaasIntegration, NaasIntegrationConfiguration
from ..integrations.LinkedInIntegration import LinkedInIntegration
from ..integrations.LinkedInIntegration import LinkedInIntegrationConfiguration

NAME = "LinkedIn Agent"
DESCRIPTION = "Access LinkedIn through your account."
MODEL = "gpt-4o"
TEMPERATURE = 0
AVATAR_URL = "https://content.linkedin.com/content/dam/me/business/en-us/amp/brand-site/v2/bg/LI-Bug.svg.original.svg"
SYSTEM_PROMPT = f"""You are a LinkedIn Agent with access to LinkedIn.
Your goal is to help users find information on LinkedIn.
To do this, you can use tools that are directly connected to LinkedIn or tools that are connected your triple store to research information from LinkedIn.

Always be clear and professional in your communication while helping users interact with LinkedIn services.
Always provide all the context (tool response, draft, etc.) to the user in your final response.
"""
SUGGESTIONS = []

def create_agent(
    agent_shared_state: AgentSharedState = None, 
    agent_configuration: AgentConfiguration = None
):
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
            system_prompt=SYSTEM_PROMPT
        )
    
    # Set model
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id=0)

    from src.core.modules.intentmapping import get_tools
    tools.extend(get_tools())

    # naas_api_key = secret.get('NAAS_API_KEY')
    # if naas_api_key:
    #     naas_integration_config = NaasIntegrationConfiguration(api_key=naas_api_key)
    #     li_at = NaasIntegration(naas_integration_config).get_secret('li_at').get('secret').get('value')
    #     JSESSIONID = NaasIntegration(naas_integration_config).get_secret('JSESSIONID').get('secret').get('value')

    # if li_at and JSESSIONID:
    #     linkedin_integration_config = LinkedInIntegrationConfiguration(li_at=li_at, JSESSIONID=JSESSIONID)
    #     linkedin_integration = LinkedInIntegration(linkedin_integration_config)
    #     tools += linkedin_integration.as_tools()
    
    return LinkedInAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools, 
        agents=agents,
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 

class LinkedInAgent(Agent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = "linkedin_agent", 
        name: str = NAME, 
        description: str = "API endpoints to call the LinkedIn agent completion.", 
        description_stream: str = "API endpoints to call the LinkedIn agent stream completion.",
        tags: list[str] = []
    ):
        return super().as_api(router, route_name, name, description, description_stream, tags)
