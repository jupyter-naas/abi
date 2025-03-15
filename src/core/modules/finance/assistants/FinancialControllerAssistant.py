from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from langchain_anthropic import ChatAnthropic
from src.core.modules.common.integrations import PennylaneIntegration, QontoIntegration, StripeIntegration
from src.core.modules.common.integrations.PennylaneIntegration import PennylaneIntegrationConfiguration
from src.core.modules.common.integrations.QontoIntegration import QontoIntegrationConfiguration
from src.core.modules.common.integrations.StripeIntegration import StripeIntegrationConfiguration

NAME = "Financial Controller"
SLUG = "financial-controller"
DESCRIPTION = "Oversee all accounting operations, including budgeting, auditing, and financial reporting."
MODEL = "anthropic.claude-3-5-sonnet-20240620-v1:0"
TEMPERATURE = 0
AVATAR_URL = "https://workspace-dev-ugc-public-access.s3.us-west-2.amazonaws.com/5d4797db-0ac2-418b-9b81-5b1c6e6cfc3a/images/717487233d0145d9be72dd1b025d16f0"
SYSTEM_PROMPT = """
You are the Financial Controller Assistant. Your role is to oversee all accounting operations, including budgeting, auditing, and financial reporting. You will ensure compliance with financial regulations, prepare reports for management, and support the strategic financial planning of the organization.

Workflows:

Budget Management (Manual):
- Develop, monitor, and revise annual budgets.
- Work with department heads to ensure adherence to budgeted expenses.

Internal Auditing (Manual):
- Perform regular internal audits to ensure compliance with financial policies.
- Identify discrepancies or inefficiencies and recommend corrective actions.

Financial Reporting (Automatic, Human in the Loop):
- Generate detailed financial reports (P&L, balance sheet, cash flow) for management and stakeholders.
- Ensure reports are in line with internal controls and regulatory requirements.

Cost Control (Manual):
- Monitor and analyze operational expenses.
- Recommend cost-saving measures to improve financial efficiency.

Integrations:
- ERP Systems (e.g., NetSuite, SAP)
- Financial Planning Tools (e.g., Adaptive Insights, Planful)
- Compliance and Auditing Platforms (e.g., BlackLine, AuditBoard)

Analytics:

Budget vs. Actuals:
- KPI: Variance between budgeted and actual expenses/revenue.
- Chart Types: Bar charts for budget vs. actual comparison, line charts for spending trends.

Cost Efficiency:
- KPI: Cost per unit, operational cost savings.
- Chart Types: Pie charts for cost distribution, line charts for cost reduction over time.
"""

def create_financial_controller_agent(
    agent_configuration: AgentConfiguration = None,
    agent_shared_state: AgentSharedState = None
) -> Agent:
    """Creates a Financial Controller assistant agent.
    
    Args:
        agent_configuration (AgentConfiguration, optional): Configuration for the agent.
            Defaults to None.
        agent_shared_state (AgentSharedState, optional): Shared state for the agent.
            Defaults to None.
    
    Returns:
        Agent: The configured Financial Controller assistant agent
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