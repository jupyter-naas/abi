from typing import Optional

from langchain_openai import ChatOpenAI
from naas_abi import secret
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)
from pydantic import SecretStr

NAME = "Agicap"
DESCRIPTION = "Expert cash flow management and financial analysis agent with access to Agicap Integration tools."
MODEL = "gpt-4.1-mini"
TEMPERATURE = 0.3
AVATAR_URL = "https://logo.clearbit.com/agicap.com"

SYSTEM_PROMPT = """# ROLE
You are Agicap, an expert financial analyst and cash flow management specialist. You possess deep expertise in:

# OBJECTIVE
Help users access data in Agicap and perform financial analysis on the data.

# CONTEXT
You operate as a professional financial analyst with access to Agicap data.

# TASKS
- Retrieve financial data from Agicap
- Perform financial analysis on retrieved data

# TOOLS
You have access to the following Agicap integration tools:
- agicap_list_companies: Get list of accessible companies with their IDs
- agicap_get_company_accounts: Get all accounts with their IDs for a company
- agicap_get_transactions: Get all transactions for a specific account
- agicap_get_balance: Get account balance information (consolidated if no account specified)
- agicap_get_debts: Get company debt information

# OPERATING GUIDELINES
1. Company Context: Always start by using `agicap_list_companies` to understand available companies
2. Account Discovery: Use `agicap_get_company_accounts` to identify relevant accounts for analysis
3. Data Integrity: Verify calculations and cross-reference multiple sources
4. Privacy: Respect data confidentiality and highlight any data inconsistencies
5. Business Focus: Transform raw financial data into strategic business intelligence

# CONSTRAINTS
- Always provide context (tool responses, analysis, etc.) in your final response
- Flag any data inconsistencies or potential errors
- Maintain strict data accuracy and validation
"""

SUGGESTIONS: list = [
    {
        "label": "💰 Analyse de trésorerie",
        "description": "Obtenir un aperçu complet de la trésorerie",
        "prompt": "Peux-tu analyser ma situation de trésorerie actuelle ?",
    },
    {
        "label": "📊 Tableau de bord financier",
        "description": "Créer un tableau de bord avec les KPIs clés",
        "prompt": "Crée un tableau de bord financier avec les indicateurs clés",
    },
    {
        "label": "🔍 Analyse des transactions",
        "description": "Analyser les transactions récentes",
        "prompt": "Analyse mes transactions récentes et identifie les tendances",
    },
    {
        "label": "⚠️ Alertes de risque",
        "description": "Identifier les risques de liquidité",
        "prompt": "Identifie les risques potentiels dans ma trésorerie",
    },
    {
        "label": "📈 Prévisions de trésorerie",
        "description": "Établir des prévisions à court terme",
        "prompt": "Établis des prévisions de trésorerie pour les 30 prochains jours",
    },
    {
        "label": "💳 Suivi des dettes",
        "description": "Analyser la situation d'endettement",
        "prompt": "Analyse ma situation d'endettement et propose des optimisations",
    },
]


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> IntentAgent:
    """Create an Agicap agent with cash flow management capabilities.

    Args:
        agent_shared_state: Shared state for the agent
        agent_configuration: Configuration for the agent

    Returns:
        IntentAgent: Configured Agicap agent or None if API keys are missing
    """
    # Set model
    model = ChatOpenAI(
        model=MODEL,
        temperature=TEMPERATURE,
        api_key=SecretStr(secret.get("OPENAI_API_KEY")),
    )

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    # Configure Agicap integration
    from naas_abi_marketplace.applications.agicap.integrations.AgicapIntegration import (
        AgicapIntegrationConfiguration,
        as_tools,
    )

    agicap_integration_config = AgicapIntegrationConfiguration(
        username=secret.get("AGICAP_USERNAME"),
        password=secret.get("AGICAP_PASSWORD"),
        bearer_token=secret.get("AGICAP_BEARER_TOKEN"),
        client_id=secret.get("AGICAP_CLIENT_ID"),
        client_secret=secret.get("AGICAP_CLIENT_SECRET"),
        api_token=secret.get("AGICAP_API_TOKEN"),
    )
    tools = as_tools(agicap_integration_config)

    # Define intents targeting specific Agicap integration tools
    intents: list = [
        # Company Discovery
        Intent(
            intent_value="lister les sociétés",
            intent_type=IntentType.TOOL,
            intent_target="agicap_list_companies",
        ),
        Intent(
            intent_value="list companies",
            intent_type=IntentType.TOOL,
            intent_target="agicap_list_companies",
        ),
        Intent(
            intent_value="quelles sont mes entreprises",
            intent_type=IntentType.TOOL,
            intent_target="agicap_list_companies",
        ),
        # Account Management
        Intent(
            intent_value="lister les comptes",
            intent_type=IntentType.TOOL,
            intent_target="agicap_get_company_accounts",
        ),
        Intent(
            intent_value="get company accounts",
            intent_type=IntentType.TOOL,
            intent_target="agicap_get_company_accounts",
        ),
        Intent(
            intent_value="comptes bancaires",
            intent_type=IntentType.TOOL,
            intent_target="agicap_get_company_accounts",
        ),
        Intent(
            intent_value="soldes des comptes",
            intent_type=IntentType.TOOL,
            intent_target="agicap_get_balance",
        ),
        Intent(
            intent_value="account balances",
            intent_type=IntentType.TOOL,
            intent_target="agicap_get_balance",
        ),
        # Transaction Analysis
        Intent(
            intent_value="historique des transactions",
            intent_type=IntentType.TOOL,
            intent_target="agicap_get_transactions",
        ),
        Intent(
            intent_value="mouvements bancaires",
            intent_type=IntentType.TOOL,
            intent_target="agicap_get_transactions",
        ),
        Intent(
            intent_value="suivi des paiements",
            intent_type=IntentType.TOOL,
            intent_target="agicap_get_transactions",
        ),
        # Debt Management
        Intent(
            intent_value="analyse des dettes",
            intent_type=IntentType.TOOL,
            intent_target="agicap_get_debts",
        ),
        Intent(
            intent_value="debt analysis",
            intent_type=IntentType.TOOL,
            intent_target="agicap_get_debts",
        ),
        Intent(
            intent_value="situation d'endettement",
            intent_type=IntentType.TOOL,
            intent_target="agicap_get_debts",
        ),
        Intent(
            intent_value="dettes en cours",
            intent_type=IntentType.TOOL,
            intent_target="agicap_get_debts",
        ),
    ]

    return AgicapAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=[],
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class AgicapAgent(IntentAgent):
    pass
