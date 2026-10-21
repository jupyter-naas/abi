"""Engine tools as LangChain tools, so an SDK agent can bind what it found by search.

Optional (extra ``engine-tools``): import only when a proxy is requested, like
``agent_tools``. The proxy holds a tool's *definition* and the plain configuration and
secret *names* the caller chose; a call goes to the engine (``ToolRegistryService.invoke``),
which runs the tool, resolves its secrets and enforces access. Nothing of the tool, and
no credential, is here. A failure reaches the model as the tool's output, so it can
recover; the engine's messages hold no secret.

    registry = module.services.tool_registry
    found = await registry.search_tools("open a github issue", limit=3)
    tools = [await registry.as_tool(m, secrets={"access_token": "GITHUB_ACCESS_TOKEN"})
             for m in found if m.availability.available]
    agent = Agent("support", "...", chat_model, tools=tools)
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from langchain_core.tools import StructuredTool, ToolException

from naas_abi_sdk.services.errors import ServiceError
from naas_abi_sdk.services.tool_registry import (
    DEFAULT_INVOKE_TIMEOUT,
    ToolDefinition,
    ToolEntry,
    ToolMatch,
)
from naas_abi_sdk.transport import RPCError

if TYPE_CHECKING:
    from naas_abi_sdk.services.tool_registry import ToolRegistryService


def model_facing_name(name: str) -> str:
    """The name the agent runtime exposes to the model (letters, digits, ``_``, ``-``)."""
    if re.match(r"^[a-zA-Z0-9_-]+$", name):
        return name
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name).replace("__", "_")


def tool_output(result: Any) -> str:
    """What the model reads: a string as it is, any other JSON value as JSON."""
    return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)


def engine_tool(
    registry: ToolRegistryService,
    tool: ToolDefinition | ToolMatch | ToolEntry,
    *,
    config: Mapping[str, Any] | None = None,
    secrets: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_INVOKE_TIMEOUT,
    name: str | None = None,
) -> StructuredTool:
    """A LangChain tool that runs ``tool`` on the engine.

    ``config``: plain values for non-secret configuration keys. ``secrets``: a
    configuration key the tool marks secret -> the name of an engine secret the engine
    allows this module to use. Both are fixed here, so the model never sees them.
    Create it inside the running module: a synchronous call is handed to the module's
    event loop.
    """
    definition = tool if isinstance(tool, ToolDefinition) else tool.definition
    if definition.remote:
        raise ValueError(
            f"'{definition.id}' is served by a module: call that module "
            "(ModuleProxy.call_tool), the engine does not run it"
        )
    fixed_config, fixed_secrets = dict(config or {}), dict(secrets or {})
    try:
        loop: asyncio.AbstractEventLoop | None = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    async def run(**arguments: Any) -> str:
        try:
            result = await registry.invoke(
                definition.id,
                arguments,
                config=fixed_config,
                secrets=fixed_secrets,
                timeout=timeout,
            )
        except (ServiceError, RPCError) as exc:
            raise ToolException(str(exc)) from exc
        return tool_output(result)

    def sync_run(**arguments: Any) -> str:
        if loop is None or not loop.is_running():
            raise RuntimeError(
                "Create engine tools inside the running module; use ainvoke for async callers"
            )
        try:
            current: asyncio.AbstractEventLoop | None = asyncio.get_running_loop()
        except RuntimeError:
            current = None
        if current is loop:
            raise RuntimeError("Use tool.ainvoke on the module event loop")
        return asyncio.run_coroutine_threadsafe(run(**arguments), loop).result()

    return StructuredTool(
        name=model_facing_name(name or definition.name),
        description=definition.description,
        args_schema=dict(definition.input_schema),
        func=sync_run,
        coroutine=run,
        handle_tool_error=True,
    )
