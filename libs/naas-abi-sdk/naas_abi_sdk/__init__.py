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
    from naas_abi_sdk.integration import (
        Integration,
        IntegrationConfiguration,
        IntegrationConnectionError,
    )
    from naas_abi_sdk.module import (
        BaseModule,
        ModuleConfiguration,
        ModuleDependencies,
        current_module,
        run_module,
    )
    from naas_abi_sdk.pipeline import (
        Pipeline,
        PipelineConfiguration,
        PipelineParameters,
    )
    from naas_abi_sdk.transport import RPCError
    from naas_abi_sdk.workflow import (
        Workflow,
        WorkflowConfiguration,
        WorkflowParameters,
    )
    from naas_abi_sdk.workflows import FlowContext, WorkflowProxy, WorkflowRun, workflow

_EXPORTS = {
    "ABIClient": "naas_abi_sdk.client",
    "Integration": "naas_abi_sdk.integration",
    "IntegrationConfiguration": "naas_abi_sdk.integration",
    "IntegrationConnectionError": "naas_abi_sdk.integration",
    "Pipeline": "naas_abi_sdk.pipeline",
    "PipelineConfiguration": "naas_abi_sdk.pipeline",
    "PipelineParameters": "naas_abi_sdk.pipeline",
    "Workflow": "naas_abi_sdk.workflow",
    "WorkflowConfiguration": "naas_abi_sdk.workflow",
    "WorkflowParameters": "naas_abi_sdk.workflow",
    "AgentDescriptor": "naas_abi_sdk.discovery",
    "AgentProxy": "naas_abi_sdk.agent",
    "AgentState": "naas_abi_sdk.agent",
    "AppDescriptor": "naas_abi_sdk.apps",
    "BaseModule": "naas_abi_sdk.module",
    "DiscoveryConfiguration": "naas_abi_sdk.discovery",
    "FlowContext": "naas_abi_sdk.workflows",
    "InvocationHandle": "naas_abi_sdk.agent",
    "ModuleConfiguration": "naas_abi_sdk.module",
    "ModelDescriptor": "naas_abi_sdk.discovery",
    "ModuleDependencies": "naas_abi_sdk.module",
    "RPCError": "naas_abi_sdk.transport",
    "SubmissionUncertain": "naas_abi_sdk.agent",
    "WorkflowProxy": "naas_abi_sdk.workflows",
    "WorkflowRun": "naas_abi_sdk.workflows",
    "current_module": "naas_abi_sdk.module",
    "run_module": "naas_abi_sdk.module",
    "workflow": "naas_abi_sdk.workflows",
}

__all__ = [
    "ABIClient",
    "AgentDescriptor",
    "AgentProxy",
    "AgentState",
    "AppDescriptor",
    "BaseModule",
    "DiscoveryConfiguration",
    "FlowContext",
    "Integration",
    "IntegrationConfiguration",
    "IntegrationConnectionError",
    "InvocationHandle",
    "ModelDescriptor",
    "ModuleConfiguration",
    "ModuleDependencies",
    "Pipeline",
    "PipelineConfiguration",
    "PipelineParameters",
    "RPCError",
    "SubmissionUncertain",
    "Workflow",
    "WorkflowConfiguration",
    "WorkflowParameters",
    "WorkflowProxy",
    "WorkflowRun",
    "current_module",
    "run_module",
    "workflow",
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
