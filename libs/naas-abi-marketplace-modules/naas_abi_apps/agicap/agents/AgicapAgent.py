"""Agicap agent: an SDK IntentAgent hosted by the remote ``agicap`` module."""

from __future__ import annotations

from typing import Any

from naas_abi_apps.agicap.integrations.AgicapIntegration import (
    AgicapIntegrationConfiguration,
    as_tools,
)
from naas_abi_apps.common.agents import build_agent, tools_prompt
from naas_abi_sdk.agents import Agent, Intent, IntentType

NAME = "Agicap"
DESCRIPTION = "Expert cash flow management and financial analysis agent with access to Agicap Integration tools."
SYSTEM_PROMPT = """<role>
You are Agicap, an expert financial analyst and cash flow management specialist. You possess deep expertise in:
</role>

<objective>
Help users access data in Agicap and perform financial analysis on the data.
</objective>

<context>
You operate within a secure environment with authenticated access to Agicap through configured credentials.
</context>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
1. Company Context: Always start by using `agicap_list_companies` to understand available companies
2. Account Discovery: Use `agicap_get_company_accounts` to identify relevant accounts for analysis
3. Data Integrity: Verify calculations and cross-reference multiple sources
4. Privacy: Respect data confidentiality and highlight any data inconsistencies
5. Business Focus: Transform raw financial data into strategic business intelligence
</operating_guidelines>

<constraints>
- Always provide context (tool responses, analysis, etc.) in your final response
- Flag any data inconsistencies or potential errors
- Maintain strict data accuracy and validation
</constraints>
"""

INTENTS: list[Intent] = [
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


def tools_for(credentials: dict[str, str]) -> list[Any]:
    """The Agicap tools, or none without any credential."""
    if not any(credentials.values()):
        return []
    return as_tools(AgicapIntegrationConfiguration(**credentials))


async def create_agent(
    engine: Any, module_id: str, *, credentials: dict[str, str], chat_model: str = ""
) -> Agent:
    tools = tools_for(credentials)
    names = {tool.name for tool in tools}
    return await build_agent(
        engine,
        module_id,
        name=NAME,
        description=DESCRIPTION,
        system_prompt=tools_prompt(SYSTEM_PROMPT, tools),
        tools=tools,
        # A tool intent without its tool would route to nothing.
        intents=[i for i in INTENTS if i.intent_target in names],
        chat_model=chat_model,
    )
