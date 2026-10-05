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
    from naas_abi_sdk.transport import RPCError

_EXPORTS = {
    "ABIClient": "naas_abi_sdk.client",
    "AgentDescriptor": "naas_abi_sdk.discovery",
    "AgentProxy": "naas_abi_sdk.agent",
    "AgentState": "naas_abi_sdk.agent",
    "BaseModule": "naas_abi_sdk.module",
    "DiscoveryConfiguration": "naas_abi_sdk.discovery",
    "InvocationHandle": "naas_abi_sdk.agent",
    "ModuleConfiguration": "naas_abi_sdk.module",
    "ModelDescriptor": "naas_abi_sdk.discovery",
    "ModuleDependencies": "naas_abi_sdk.module",
    "RPCError": "naas_abi_sdk.transport",
    "SubmissionUncertain": "naas_abi_sdk.agent",
    "current_module": "naas_abi_sdk.module",
    "run_module": "naas_abi_sdk.module",
}

__all__ = [
    "ABIClient",
    "AgentDescriptor",
    "AgentProxy",
    "AgentState",
    "BaseModule",
    "DiscoveryConfiguration",
    "InvocationHandle",
    "ModelDescriptor",
    "ModuleConfiguration",
    "ModuleDependencies",
    "RPCError",
    "SubmissionUncertain",
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
