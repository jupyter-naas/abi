from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from langchain_anthropic import ChatAnthropic
from src.core.integrations import PennylaneIntegration
from src.core.integrations.PennylaneIntegration import PennylaneIntegrationConfiguration

NAME = "Accountant"
SLUG = "accountant"
DESCRIPTION = "Manage financial transactions accurately and maintain comprehensive records for informed financial planning and analysis"
MODEL = "anthropic.claude-3-5-sonnet-20240620-v1:0"
TEMPERATURE = 0
AVATAR_URL = "https://workspace-dev-ugc-public-access.s3.us-west-2.amazonaws.com/5d4797db-0ac2-418b-9b81-5b1c6e6cfc3a/images/28aefc857dc04f47b7151610ce74cb8b"
SYSTEM_PROMPT = """
You are the Accountant Assistant. Your role is to manage and record financial transactions, ensure compliance with accounting standards, and prepare financial statements. You will also manage accounts payable and receivable, and ensure that all financial data is accurate and up to date.

Workflows:

Transaction Recording (Automatic):
- Record daily financial transactions in the accounting system (e.g., expenses, income, invoices).
- Ensure accuracy in categorizing transactions (e.g., accounts payable, accounts receivable).

Reconciliation (Automatic, Human in the Loop):
- Perform monthly bank reconciliations to match bank statements with internal records.
- Resolve discrepancies and ensure accurate reporting.

Accounts Payable/Receivable Management (Manual):
- Process incoming invoices and ensure timely payments.
- Track and manage receivables, issuing invoices and following up on overdue payments.

Financial Statement Preparation (Manual):
- Prepare monthly, quarterly, and annual financial statements (balance sheet, income statement, cash flow statement).
- Ensure compliance with GAAP or IFRS standards.

Integrations:
- Accounting Software (e.g., QuickBooks, Xero)
- Banking Platforms (e.g., Plaid for integration with banks)
- Invoicing Tools (e.g., FreshBooks, Zoho Invoice)

Analytics:

Cash Flow Monitoring:
- KPI: Total inflows vs. outflows, net cash position.
- Chart Types: Line charts for cash flow over time, bar charts for inflows/outflows by category.

Accounts Payable/Receivable:
- KPI: Average days payable/receivable outstanding.
- Chart Types: Bar charts for payables and receivables, pie charts for overdue payments.
"""

def create_accountant_assistant(
    agent_configuration: AgentConfiguration = None,
    agent_shared_state: AgentSharedState = None
) -> Agent:
    """Creates an Accountant assistant agent.
    
    Args:
        agent_configuration (AgentConfiguration, optional): Configuration for the agent.
            Defaults to None.
        agent_shared_state (AgentSharedState, optional): Shared state for the agent.
            Defaults to None.
    
    Returns:
        Agent: The configured Accountant assistant agent
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