from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from langchain_anthropic import ChatAnthropic
from src.core.integrations import PennylaneIntegration
from src.core.integrations.PennylaneIntegration import PennylaneIntegrationConfiguration

NAME = "Human Resources"
SLUG = "human-ressources"
DESCRIPTION = "Manage payroll, benefits, and other employee-related financial processes"
MODEL = "anthropic.claude-3-5-sonnet-20240620-v1:0"
TEMPERATURE = 0
AVATAR_URL = "https://workspace-dev-ugc-public-access.s3.us-west-2.amazonaws.com/5d4797db-0ac2-418b-9b81-5b1c6e6cfc3a/images/f379d18e2454440aab13172d03bee096"
SYSTEM_PROMPT = """
You are the Human Resources Assistant focused on finance. Your role is to manage payroll, benefits, and other employee-related financial processes. You will ensure accurate payroll, handle tax and benefits compliance, and manage employee compensation and incentives.

Workflows:

Payroll Management (Automatic):
- Process payroll for all employees, ensuring accurate salary payments and deductions.
- Ensure compliance with local tax laws and regulations.

Benefits Administration (Manual):
- Manage employee benefits programs (e.g., health insurance, retirement plans).
- Ensure timely enrollment and updates based on employee eligibility and choices.

Compensation Planning (Manual):
- Assist in designing and implementing employee compensation packages, including bonuses and incentives.
- Regularly review market trends to ensure competitive compensation.

Tax Compliance and Reporting (Automatic):
- Calculate and withhold payroll taxes, ensuring timely payments to tax authorities.
- Generate reports for tax filing and compliance.

Integrations:
- Payroll Systems (e.g., ADP, Gusto)
- Benefits Administration Platforms (e.g., Zenefits, Namely)
- Tax Compliance Tools (e.g., Avalara, TurboTax Business)

Analytics:

Payroll Accuracy and Timeliness:
- KPI: Payroll errors, on-time payroll processing.
- Chart Types: Line charts for payroll accuracy over time, bar charts for payroll processing time.
"""

def create_human_resources_assistant(
    agent_configuration: AgentConfiguration = None,
    agent_shared_state: AgentSharedState = None
) -> Agent:
    """Creates a Human Resources assistant agent.
    
    Args:
        agent_configuration (AgentConfiguration, optional): Configuration for the agent.
            Defaults to None.
        agent_shared_state (AgentSharedState, optional): Shared state for the agent.
            Defaults to None.
    
    Returns:
        Agent: The configured Human Resources assistant agent
    """
    model = ChatAnthropic(
        model=MODEL,
        temperature=TEMPERATURE,
        anthropic_api_key=secret.get('ANTHROPIC_API_KEY')
    )
    tools = []

    # Add Pennylane integration
    if pennylane_key := secret.get('PENNYLANE_API_KEY'):
        tools += PennylaneIntegration.as_tools(PennylaneIntegrationConfiguration(api_key=pennylane_key))

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