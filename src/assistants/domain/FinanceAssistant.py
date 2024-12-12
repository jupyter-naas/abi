from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.integrations import StripeIntegration

FINANCE_ASSISTANT_INSTRUCTIONS = '''You are a Financial Assistant with access to comprehensive financial data sources. 

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
    
    if stripe_key := secret.get('STRIPE_API_KEY'):
        tools += StripeIntegration.as_tools(StripeIntegration.StripeIntegrationConfiguration(api_key=stripe_key))
    
    # Use provided configuration or create default one
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=FINANCE_ASSISTANT_INSTRUCTIONS
        )
    
    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()
    
    return Agent(
        name="finance_assistant", 
        description="Use for financial analysis and insights",
        chat_model=model, 
        tools=tools, 
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 