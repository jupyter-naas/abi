"""Agents written like naas_abi_core agents, run by SDK modules over NATS.

Install ``naas-abi-sdk[agent]``. Importing this package loads LangChain and
LangGraph; never import it from ``naas_abi_sdk/__init__`` or the base catalog.
"""

from naas_abi_sdk.agents.agent import (
    ABIAgentState,
    Agent,
    AgentConfiguration,
    AgentSharedState,
)
from naas_abi_sdk.agents.intent_agent import IntentAgent
from naas_abi_sdk.agents.intents import DEFAULT_INTENTS, Intent, IntentScope, IntentType

__all__ = [
    "DEFAULT_INTENTS",
    "ABIAgentState",
    "Agent",
    "AgentConfiguration",
    "AgentSharedState",
    "Intent",
    "IntentAgent",
    "IntentScope",
    "IntentType",
]
