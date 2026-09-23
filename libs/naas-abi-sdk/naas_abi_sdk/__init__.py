"""Independent protobuf clients for ABI services over NATS."""

from naas_abi_sdk.agent import (
    AgentProxy,
    AgentState,
    InvocationHandle,
    SubmissionUncertain,
)
from naas_abi_sdk.client import ABIClient
from naas_abi_sdk.discovery import AgentDescriptor, DiscoveryConfiguration
from naas_abi_sdk.module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
    current_module,
    run_module,
)
from naas_abi_sdk.transport import RPCError

__all__ = [
    "ABIClient",
    "AgentDescriptor",
    "AgentProxy",
    "AgentState",
    "BaseModule",
    "DiscoveryConfiguration",
    "InvocationHandle",
    "ModuleConfiguration",
    "ModuleDependencies",
    "RPCError",
    "SubmissionUncertain",
    "current_module",
    "run_module",
]
