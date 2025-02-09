from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from fastapi import APIRouter
from src.core.assistants.foundation.SupportAssistant import create_support_assistant
from src.core.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.core.integrations import AgicapIntegration, PennylaneIntegration, MercuryIntegration, QontoIntegration, StripeIntegration
from src.core.integrations.AgicapIntegration import AgicapIntegrationConfiguration
from src.core.integrations.PennylaneIntegration import PennylaneIntegrationConfiguration
from src.core.integrations.MercuryIntegration import MercuryIntegrationConfiguration
from src.core.integrations.StripeIntegration import StripeIntegrationConfiguration
from src.core.integrations.QontoIntegration import QontoIntegrationConfiguration

DESCRIPTION = "A Financial Assistant that analyzes transactions and provides financial insights."
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/finance_management.png"
SYSTEM_PROMPT = f'''
You are a Financial Assistant with access to comprehensive financial data sources. 

Your primary objective is to analyze and optimize financial transactions, ensuring you identify key insights and trends to guide financial strategies. 
Leverage the data to decipher patterns, customer behavior, and payment methods to strategize on revenue growth and financial operations.
Your ultimate goal is to maximize revenue, minimize risks, and contribute to the overall financial success of the organization.

Start each conversation by:
1. Introducing yourself
2. Displaying this image showing financial metrics:
   ![Finance](https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/finance_trend.png)

Always:
1. Use Stripe data for transaction management and insights
2. Provide structured, markdown-formatted responses
3. Include metrics and performance indicators in your analysis
4. Be casual but professional in your communication

RESPONSIBILITIES
-----------------
{RESPONSIBILITIES_PROMPT}
'''

def create_finance_assistant(
    agent_shared_state: AgentSharedState = None, 
    agent_configuration: AgentConfiguration = None
) -> Agent:
    # Init
    tools = []
    agents = []

    # Set model
    model = ChatOpenAI(
        model="gpt-4o", 
        temperature=0, 
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

    # Add tools
    if secret.get('AGICAP_USERNAME') and secret.get('AGICAP_PASSWORD') and secret.get('AGICAP_BEARER_TOKEN') and secret.get('AGICAP_CLIENT_ID') and secret.get('AGICAP_CLIENT_SECRET') and secret.get('AGICAP_API_TOKEN'):    
        integration_config = AgicapIntegrationConfiguration(
            username=secret.get('AGICAP_USERNAME'),
            password=secret.get('AGICAP_PASSWORD'),
            bearer_token=secret.get('AGICAP_BEARER_TOKEN'),
            client_id=secret.get('AGICAP_CLIENT_ID'),
            client_secret=secret.get('AGICAP_CLIENT_SECRET'),
            api_token=secret.get('AGICAP_API_TOKEN')
        )
        tools += AgicapIntegration.as_tools(integration_config)

    if pennylane_key := secret.get('PENNYLANE_API_KEY'):
        integration_config = PennylaneIntegrationConfiguration(
            api_key=pennylane_key
        )
        tools += PennylaneIntegration.as_tools(integration_config)

    if mercure_key := secret.get('MERCURY_API_TOKEN'):
        integration_config = MercuryIntegrationConfiguration(
            api_key=mercure_key
        )
        tools += MercuryIntegration.as_tools(integration_config)
    
    if secret.get('QONTO_SECRET_KEY') and secret.get('QONTO_ORGANIZATION_SLUG'):
        integration_config = QontoIntegrationConfiguration(
            secret_key=secret.get('QONTO_SECRET_KEY'),
            organization_slug=secret.get('QONTO_ORGANIZATION_SLUG')
        )
        tools += QontoIntegration.as_tools(integration_config)

    if stripe_key := secret.get('STRIPE_API_KEY'):
        integration_config = StripeIntegrationConfiguration(
            api_key=stripe_key
        )
        tools += StripeIntegration.as_tools(integration_config)

    # Add agents
    agents.append(create_support_assistant(AgentSharedState(thread_id=1), agent_configuration))
    
    return FinanceAssistant(
        name="finance_assistant", 
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
        name: str = "Finance Assistant", 
        description: str = "API endpoints to call the Finance assistant completion.", 
        description_stream: str = "API endpoints to call the Finance assistant stream completion.",
        tags: list[str] = []
    ):
        return super().as_api(router, route_name, name, description, description_stream, tags)