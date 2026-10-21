"""A tool a module serves, as a LangChain tool the agent runtime can call.

The binding holds nothing of the module but its definition: building the tool
captures the caller's identity and the plain configuration its record wrote, and
a call goes to the module over NATS (``IRemoteToolInvoker``). The binding's own
default configuration is empty: the engine has no value to give a module, which
holds its own credentials. Failures reach the model as the tool's output (a
``ToolException``), so it can recover.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from langchain_core.tools import StructuredTool, ToolException
from naas_abi_core.services.tool_registry.adapters.primary.LangChainToolPublisher import (
    model_facing_name,
)
from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    IRemoteToolInvoker,
    RemoteToolError,
    ToolConfigurationError,
    ToolContext,
    ToolDefinition,
    ToolResolutionError,
)


def tool_output(result: Any) -> str:
    """What the model reads: a string as it is, any other JSON value as JSON."""
    return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)


class RemoteToolBinding:
    default_config: Mapping[str, Any] = MappingProxyType({})

    def __init__(
        self,
        definition: ToolDefinition,
        contract_major: int,
        invoker: IRemoteToolInvoker,
    ) -> None:
        self._definition = definition
        self._contract_major = contract_major
        self._invoker = invoker

    def create(self, context: ToolContext, config: Mapping[str, Any]) -> StructuredTool:
        definition = self._definition
        declared = {requirement.key for requirement in definition.requirements.config}
        unknown = sorted(set(config) - declared)
        if unknown:
            raise ToolResolutionError(
                f"Tool '{definition.id}' takes no configuration {unknown}: it is served "
                f"by a module, which declares only {sorted(declared)}."
            )
        missing = [
            key
            for key in definition.required_config_keys()
            if config.get(key) in (None, "")
        ]
        if missing:
            raise ToolConfigurationError(str(definition.id), missing)
        values = dict(config)
        invoker, major = self._invoker, self._contract_major

        def run(**arguments: Any) -> str:
            try:
                return tool_output(
                    invoker.invoke(definition, major, arguments, values, context)
                )
            except RemoteToolError as exc:
                raise ToolException(str(exc)) from exc

        async def arun(**arguments: Any) -> str:
            try:
                return tool_output(
                    await invoker.ainvoke(definition, major, arguments, values, context)
                )
            except RemoteToolError as exc:
                raise ToolException(str(exc)) from exc

        return StructuredTool(
            name=model_facing_name(definition.name),
            description=definition.description,
            args_schema=dict(definition.input_schema),
            func=run,
            coroutine=arun,
            handle_tool_error=True,
        )
