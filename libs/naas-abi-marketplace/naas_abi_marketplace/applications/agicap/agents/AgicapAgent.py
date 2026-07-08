from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)


class AgicapAgent(IntentAgent):
    name: str = "Agicap"
    description: str = "Expert cash flow management and financial analysis agent with access to Agicap Integration tools."
    avatar_url: str = "https://agicap.com/favicon.ico"
    system_prompt: str = """<role>
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

    suggestions: list = []

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "AgicapAgent":
        from naas_abi_marketplace.applications.agicap import ABIModule
        from naas_abi_marketplace.applications.agicap.integrations.AgicapIntegration import (
            AgicapIntegrationConfiguration,
            as_tools,
        )



        abi_module = ABIModule.get_instance()

        registry = abi_module.engine.services.model_registry
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()
        embedding_model = registry.get_default_embedding_model().model

        module = ABIModule.get_instance()
        agicap_integration_config = AgicapIntegrationConfiguration(
            username=module.configuration.agicap_username,
            password=module.configuration.agicap_password,
            bearer_token=module.configuration.agicap_bearer_token,
            client_id=module.configuration.agicap_client_id,
            client_secret=module.configuration.agicap_client_secret,
            api_token=module.configuration.agicap_api_token,
        )
        tools = as_tools(agicap_integration_config)

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

        system_prompt = cls.system_prompt.replace(
            "[TOOLS]",
            "\n".join([f"- {tool.name}: {tool.description}" for tool in tools]),
        )
        if agent_configuration is None:
            agent_configuration = AgentConfiguration(system_prompt=system_prompt)
        if agent_shared_state is None:
            agent_shared_state = AgentSharedState(thread_id="0")

        return cls(
            name=cls.name,
            description=cls.description,
            chat_model=chat_model,
            embedding_model=embedding_model,
            tools=tools,
            agents=[],
            intents=intents,
            state=agent_shared_state,
            configuration=agent_configuration,
            memory=None,
        )
