"""The LangChain tool a remote tool resolves to: it calls the module, never holds a secret."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from typing import Any

import pytest
from langchain_core.utils.function_calling import convert_to_openai_tool
from naas_abi_core.services.tool_registry.adapters.primary.RemoteToolBinding import (
    RemoteToolBinding,
)
from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    ConfigRequirement,
    IRemoteToolInvoker,
    PublishedTool,
    RemoteToolError,
    ToolConfigurationError,
    ToolContext,
    ToolDefinition,
    ToolRequirements,
    ToolResolutionError,
)
from naas_abi_core.services.tool_registry.ToolRegistryService import (
    ToolRegistryService,
)

DEFINITION = ToolDefinition(
    namespace="acme.crm",
    name="lookup",
    description="Look a customer up by email.",
    module="acme.crm",
    remote=True,
    input_schema={
        "type": "object",
        "properties": {"email": {"type": "string", "description": "Customer email."}},
        "required": ["email"],
    },
    requirements=ToolRequirements(config=(ConfigRequirement(key="region"),)),
)


class Invoker(IRemoteToolInvoker):
    def __init__(self, result: Any = None, error: RemoteToolError | None = None):
        self.result, self.error = result, error
        self.calls: list[tuple[Any, ...]] = []

    def invoke(self, definition, contract_major, arguments, config, context):
        self.calls.append(
            (definition, contract_major, dict(arguments), dict(config), context)
        )
        if self.error:
            raise self.error
        return self.result

    async def ainvoke(self, definition, contract_major, arguments, config, context):
        return self.invoke(definition, contract_major, arguments, config, context)


def resolve(invoker, config: Mapping[str, Any] | None = None, **context):
    registry = ToolRegistryService()
    registry.publish(
        "acme.crm",
        [PublishedTool(DEFINITION, RemoteToolBinding(DEFINITION, 3, invoker))],
    )
    return registry.resolve(
        "acme.crm/lookup",
        ToolContext(**context),
        config={"region": "eu", **(config or {})},
    )


def test_the_tool_has_the_modules_contract_and_calls_it_as_the_caller():
    invoker = Invoker({"id": 7, "tier": "gold"})
    tool = resolve(invoker, user_id="user-7", workspace_id="ws-1")
    assert tool.name == "lookup"
    spec = convert_to_openai_tool(tool)["function"]
    assert spec["name"] == "lookup"
    assert spec["parameters"]["required"] == ["email"]
    assert spec["parameters"]["properties"]["email"]["description"] == "Customer email."
    out = tool.invoke({"email": "a@b.c"})
    # A JSON result reads as JSON; a string as it is.
    assert json.loads(out) == {"id": 7, "tier": "gold"}
    ((definition, major, arguments, config, context),) = invoker.calls
    assert (definition.id, major, arguments, config) == (
        DEFINITION.id,
        3,
        {"email": "a@b.c"},
        {"region": "eu"},
    )
    assert (context.user_id, context.workspace_id) == ("user-7", "ws-1")
    assert resolve(Invoker("plain text")).invoke({"email": "a@b.c"}) == "plain text"


def test_the_async_path_calls_the_module_too():
    invoker = Invoker({"ok": True})
    tool = resolve(invoker)
    assert json.loads(asyncio.run(tool.ainvoke({"email": "a@b.c"}))) == {"ok": True}
    assert len(invoker.calls) == 1


def test_a_failure_is_the_tools_output_for_the_model_to_read():
    tool = resolve(Invoker(error=RemoteToolError("TOOL_ERROR", "Customer is archived")))
    assert tool.invoke({"email": "a@b.c"}) == "TOOL_ERROR: Customer is archived"
    assert asyncio.run(tool.ainvoke({"email": "a@b.c"})) == (
        "TOOL_ERROR: Customer is archived"
    )


def test_a_binding_holds_no_value_of_its_own():
    assert dict(RemoteToolBinding(DEFINITION, 1, Invoker()).default_config) == {}


def test_configuration_the_module_does_not_declare_is_refused():
    registry = ToolRegistryService()
    registry.publish(
        "acme.crm",
        [PublishedTool(DEFINITION, RemoteToolBinding(DEFINITION, 1, Invoker()))],
    )
    with pytest.raises(ToolResolutionError, match="api_key"):
        registry.resolve(
            "acme.crm/lookup",
            ToolContext(),
            config={"region": "eu", "api_key": "sk-live"},
        )
    with pytest.raises(ToolConfigurationError, match="region"):
        registry.resolve("acme.crm/lookup", ToolContext())
