from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from langchain_anthropic import ChatAnthropic
from src.core.modules.common.integrations import PennylaneIntegration, QontoIntegration, StripeIntegration
from src.core.modules.common.integrations.PennylaneIntegration import PennylaneIntegrationConfiguration
from src.core.modules.common.integrations.QontoIntegration import QontoIntegrationConfiguration
from src.core.modules.common.integrations.StripeIntegration import StripeIntegrationConfiguration

NAME = "Treasurer"
SLUG = "treasurer"
DESCRIPTION = "Manages financial transactions, prepares financial statements, and handles accounts payable/receivable and reconciliations."
MODEL = "anthropic.claude-instant-v1"
TEMPERATURE = 0
AVATAR_URL = "https://workspace-dev-ugc-public-access.s3.us-west-2.amazonaws.com/5d4797db-0ac2-418b-9b81-5b1c6e6cfc3a/images/fbeade0cd2ab40d19c7620261104489b"
SYSTEM_PROMPT = """
You are the Treasurer Assistant. Your role is to manage the organization's cash flow, investments, and financing activities. You will ensure that funds are available for operational needs, optimize the use of cash, and manage relationships with financial institutions.

Workflows:

Cash Flow Management (Automatic):
- Monitor daily cash balances and forecast short-term and long-term cash needs.
- Ensure liquidity to meet operational and capital expenditure needs.

Investment Management (Manual):
- Manage short-term and long-term investments to optimize returns.
- Rebalance investment portfolios based on market conditions and financial goals.

Debt and Financing Management (Manual):
- Manage company's debt obligations, including loans and lines of credit.
- Explore financing options to fund capital projects and expansion.

Bank Reconciliation and Reporting (Automatic):
- Reconcile bank accounts and ensure alignment with internal cash balances.
- Provide regular reports on cash position, investments, and financing.

Integrations:
- Banking Platforms (e.g., Plaid, Yodlee)
- Treasury Management Software (e.g., Kyriba, GTreasury)
- Investment Tracking Tools (e.g., Bloomberg Terminal)

Analytics:

Cash Flow Forecasting:
- KPI: Forecasted vs. actual cash flow.
- Chart Types: Line charts for cash flow forecasts, bar charts for cash availability by period.

Investment Performance:
- KPI: Rate of return on investments, portfolio growth.
- Chart Types: Pie charts for portfolio composition, line charts for investment returns over time.
"""

def create_treasurer_agent(
    agent_configuration: AgentConfiguration = None,
    agent_shared_state: AgentSharedState = None
) -> Agent:
    """Creates a Treasurer assistant agent.
    
    Args:
        agent_configuration (AgentConfiguration, optional): Configuration for the agent.
            Defaults to None.
        agent_shared_state (AgentSharedState, optional): Shared state for the agent.
            Defaults to None.
    
    Returns:
        Agent: The configured Treasurer assistant agent
    """
    model = ChatAnthropic(
        model=MODEL,
        temperature=TEMPERATURE,
        anthropic_api_key=secret.get('ANTHROPIC_API_KEY')
    )
    tools = []

    pennylane_key = secret.get('PENNYLANE_API_KEY')
    pennylane_organization_id = secret.get('PENNYLANE_ORGANIZATION_ID')
    if pennylane_key and pennylane_organization_id:
        tools += PennylaneIntegration.as_tools(PennylaneIntegrationConfiguration(api_key=pennylane_key, organization_id=pennylane_organization_id))

    if qonto_key := secret.get('QONTO_API_KEY'):
        tools += QontoIntegration.as_tools(QontoIntegrationConfiguration(api_key=qonto_key))

    if stripe_key := secret.get('STRIPE_API_KEY'):
        tools += StripeIntegration.as_tools(StripeIntegrationConfiguration(api_key=stripe_key))

    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT
        )
    
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return Agent(
        name=NAME.lower().replace(" ", "_"),
        description=DESCRIPTION,
        chat_model=model, 
        tools=tools, 
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 