"""Independent protobuf clients for ABI services over NATS."""

from naas_abi_sdk.client import ABIClient
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
    "BaseModule",
    "ModuleConfiguration",
    "ModuleDependencies",
    "RPCError",
    "current_module",
    "run_module",
]
