from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from fastapi import APIRouter
from src.core.modules.support.assistants.SupportAssistant import create_agent as create_support_agent
from src.core.modules.common.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT
from src.core.modules.common.integrations import MercuryIntegration
from src.core.modules.common.integrations.MercuryIntegration import MercuryIntegrationConfiguration

NAME = "Finance Assistant"
DESCRIPTION = "Analyzes financial data and delivers strategic insights. Empowers financial teams with data-driven recommendations."
MODEL = "o3-mini"
TEMPERATURE = 1
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/finance_management.png"
SYSTEM_PROMPT = f"""You are a financial expert who helps teams make data-driven decisions. Your goal is to analyze financial data and provide actionable insights that improve financial strategies.

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

def create_agent(
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
            system_prompt=SYSTEM_PROMPT
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id=0)

    if mercure_key := secret.get('MERCURY_API_TOKEN'):
        integration_config = MercuryIntegrationConfiguration(
            api_key=mercure_key
        )
        tools += MercuryIntegration.as_tools(integration_config)

    # Add agents
    agents.append(create_support_agent(AgentSharedState(thread_id=1), agent_configuration))
    
    return FinanceAssistant(
        name="finance_agent", 
        description=DESCRIPTION,
        chat_model=model, 
        tools=tools, 
        agents=agents,
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 

class FinanceAssistant(Agent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = "finance", 
        name: str = NAME, 
        description: str = "API endpoints to call the Finance assistant completion.", 
        description_stream: str = "API endpoints to call the Finance assistant stream completion.",
        tags: list[str] = []
    ):
        return super().as_api(router, route_name, name, description, description_stream, tags)