from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.integrations import AgicapIntegration, PennylaneIntegration, MercuryIntegration, QontoIntegration, StripeIntegration
from src.integrations.AgicapIntegration import AgicapIntegrationConfiguration
from src.integrations.PennylaneIntegration import PennylaneIntegrationConfiguration
from src.integrations.MercuryIntegration import MercuryIntegrationConfiguration
from src.integrations.StripeIntegration import StripeIntegrationConfiguration
from src.integrations.QontoIntegration import QontoIntegrationConfiguration

DESCRIPTION = "A Financial Assistant that analyzes transactions and provides financial insights."
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/finance_management.png"
SYSTEM_PROMPT = '''
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
'''

def create_finance_assistant(
        agent_shared_state: AgentSharedState = None, 
        agent_configuration: AgentConfiguration = None
    ) -> Agent:
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=secret.get('OPENAI_API_KEY'))
    tools = []

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

    if mercure_key := secret.get('MERCURY_API_KEY'):
        integration_config = MercuryIntegrationConfiguration(
            api_key=mercure_key
        )
        tools += MercuryIntegration.as_tools(integration_config)
    
    if qonto_key := secret.get('QONTO_API_KEY'):
        integration_config = QontoIntegrationConfiguration(
            api_key=qonto_key
        )
        tools += QontoIntegration.as_tools(integration_config)

    if stripe_key := secret.get('STRIPE_API_KEY'):
        integration_config = StripeIntegrationConfiguration(
            api_key=stripe_key
        )
        tools += StripeIntegration.as_tools(integration_config)
    
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT
        )
    
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()
    
    return Agent(
        name="finance_assistant", 
        description=DESCRIPTION,
        chat_model=model, 
        tools=tools, 
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 