"""
Bitcoin Workflow Module

Provides workflows for generating simulated Bitcoin transaction data and executing queries.
"""

from src.custom.bitcoin_agent.workflow.ChatBitcoinAgentWorkflow import (
    ChatBitcoinAgentWorkflow,
    ChatBitcoinAgentWorkflowConfiguration,
    ChatBitcoinAgentWorkflowParameters,
    BalanceQueryParameters,
    SparqlQueryParameters,
    NaturalLanguageQueryParameters
)

from src.custom.bitcoin_agent.workflow.BitcoinTransactionWorkflow import (
    BitcoinTransactionWorkflow,
    BitcoinTransactionWorkflowConfiguration,
    BitcoinTransactionWorkflowParameters
) 