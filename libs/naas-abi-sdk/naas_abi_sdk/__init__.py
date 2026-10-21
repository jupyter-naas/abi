"""Independent protobuf clients for ABI services over NATS.

Public names load lazily, so stdlib-only submodules (``naas_abi_sdk.jobs``) can
be imported where the NATS client is not installed.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from naas_abi_sdk.agent import (
        AgentProxy,
        AgentState,
        InvocationHandle,
        SubmissionUncertain,
    )
    from naas_abi_sdk.apps import AppDescriptor
    from naas_abi_sdk.client import ABIClient
    from naas_abi_sdk.discovery import (
        AgentDescriptor,
        DiscoveryConfiguration,
        ModelDescriptor,
    )
    from naas_abi_sdk.module import (
        BaseModule,
        ModuleConfiguration,
        ModuleDependencies,
        current_module,
        run_module,
    )
    from naas_abi_sdk.tools import (
        ToolCall,
        ToolCaller,
        ToolConfig,
        ToolDescriptor,
        ToolError,
    )
    from naas_abi_sdk.transport import RPCError

_EXPORTS = {
    "ABIClient": "naas_abi_sdk.client",
    "AgentDescriptor": "naas_abi_sdk.discovery",
    "AgentProxy": "naas_abi_sdk.agent",
    "AgentState": "naas_abi_sdk.agent",
    "AppDescriptor": "naas_abi_sdk.apps",
    "BaseModule": "naas_abi_sdk.module",
    "DiscoveryConfiguration": "naas_abi_sdk.discovery",
    "InvocationHandle": "naas_abi_sdk.agent",
    "ModuleConfiguration": "naas_abi_sdk.module",
    "ModelDescriptor": "naas_abi_sdk.discovery",
    "ModuleDependencies": "naas_abi_sdk.module",
    "RPCError": "naas_abi_sdk.transport",
    "SubmissionUncertain": "naas_abi_sdk.agent",
    "ToolCall": "naas_abi_sdk.tools",
    "ToolCaller": "naas_abi_sdk.tools",
    "ToolConfig": "naas_abi_sdk.tools",
    "ToolDescriptor": "naas_abi_sdk.tools",
    "ToolError": "naas_abi_sdk.tools",
    "current_module": "naas_abi_sdk.module",
    "run_module": "naas_abi_sdk.module",
}

__all__ = [
    "ABIClient",
    "AgentDescriptor",
    "AgentProxy",
    "AgentState",
    "AppDescriptor",
    "BaseModule",
    "DiscoveryConfiguration",
    "InvocationHandle",
    "ModelDescriptor",
    "ModuleConfiguration",
    "ModuleDependencies",
    "RPCError",
    "SubmissionUncertain",
    "ToolCall",
    "ToolCaller",
    "ToolConfig",
    "ToolDescriptor",
    "ToolError",
    "current_module",
    "run_module",
]


def __getattr__(name: str) -> Any:
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module 'naas_abi_sdk' has no attribute {name!r}")
    value = getattr(import_module(module), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *_EXPORTS})
