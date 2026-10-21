"""Finds the tools SDK modules serve, and runs them, over NATS.

``IRemoteToolDirectory`` reads discovery (``abi.discovery.<project>.v1``) as the
engine's own process; ``IRemoteToolInvoker`` calls a ready instance of the module
on ``abi.mod.<project>.<instance>.tool.<name>.invoke`` (``abi.tool.v1``) with a
token bound to that instance. One attempt per call: a tool may have side effects,
and a timeout does not prove it did not run. The connections open on first use,
on the engine's NATS runtime loop.

Nothing here reads the engine's secrets but the project's signing key, which signs
the token (never sent as such). The request carries the caller's user and
workspace, the tool's arguments and the record's plain configuration.
"""

from __future__ import annotations

import json
import random
import threading
from collections.abc import Mapping
from typing import Any

from naas_abi_core import logger
from naas_abi_core.engine import nats_runtime
from naas_abi_core.engine.nats_auth import ServiceTokenSource
from naas_abi_core.engine.nats_naming import connection_name
from naas_abi_core.services.tool_registry.adapters.tool_registry_nats_codec import (
    definition_from_pb,
)
from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    IRemoteToolDirectory,
    IRemoteToolInvoker,
    RemoteModuleTools,
    RemoteToolDirectoryError,
    RemoteToolError,
    ToolContext,
    ToolDefinition,
    ToolRegistryError,
)
from naas_abi_proto.tool.v1 import tool_pb2 as pb
from naas_abi_sdk.discovery import DiscoveryClient, ModuleInstance
from naas_abi_sdk.tools import (
    MAX_ARGUMENTS_BYTES,
    MAX_CONFIG_BYTES,
    ModuleToolClient,
    tool_subject,
)
from naas_abi_sdk.transport import RPCError, Transport
from nats.errors import Error as NATSError
from nats.errors import NoRespondersError

PAGE = 100
# Pages of instances to read before giving up: a registry this large is a fault.
MAX_PAGES = 100
DISCOVERY_TIMEOUT_SECONDS = 10.0
MAX_ERROR_CHARACTERS = 1024


def _definitions(instance: ModuleInstance) -> tuple[ToolDefinition, ...]:
    found = []
    for tool in instance.tools:
        try:
            definition = definition_from_pb(tool.to_pb(instance.module_id))
        except (ToolRegistryError, RecursionError) as exc:
            logger.warning(
                f"Remote tools: '{instance.module_id}' tool '{tool.name}' skipped: {exc}"
            )
            continue
        found.append(definition.model_copy(update={"remote": True}))
    return tuple(found)


class RemoteToolsSecondaryAdapterNATS(IRemoteToolDirectory, IRemoteToolInvoker):
    def __init__(
        self,
        url: str,
        secret: str,
        project: str,
        identity: str = "engine",
        *,
        call_timeout_seconds: float = 120.0,
    ) -> None:
        self.project = project
        self.call_timeout_seconds = call_timeout_seconds
        self._connection = (url, secret, identity)
        self._discovery: DiscoveryClient | None = None
        self._tools: Transport | None = None
        self._lock = threading.Lock()

    def _clients(self) -> tuple[DiscoveryClient, Transport]:
        with self._lock:
            if self._discovery is None or self._tools is None:
                url, secret, identity = self._connection
                # Calls to a module carry a token bound to its instance.
                source = ServiceTokenSource(identity, secret)
                discovery = Transport(
                    url,
                    source,
                    timeout=DISCOVERY_TIMEOUT_SECONDS,
                    name=connection_name("abi-engine:remote_tools"),
                )
                self._tools = Transport(
                    url,
                    source,
                    timeout=self.call_timeout_seconds,
                    name=connection_name("abi-engine:remote_tool_calls"),
                )
                self._discovery = DiscoveryClient(discovery, self.project)
            return self._discovery, self._tools

    # -------------------------------------------------------------- directory
    def list_modules(self) -> list[RemoteModuleTools]:
        try:
            return nats_runtime.run_coro(
                self._list(), timeout=DISCOVERY_TIMEOUT_SECONDS * 3
            )
        except (RPCError, NATSError, OSError, TimeoutError, RuntimeError) as exc:
            # RuntimeError: the engine's NATS runtime is closed (shutdown in progress).
            raise RemoteToolDirectoryError(f"discovery did not answer: {exc}") from exc

    async def _list(self) -> list[RemoteModuleTools]:
        discovery, _ = self._clients()
        ready: dict[tuple[str, int], ModuleInstance] = {}
        after = ""
        for _ in range(MAX_PAGES):
            instances, after = await discovery.list_modules(
                limit=PAGE, after_instance_id=after
            )
            for instance in instances:
                if instance.status == "READY" and instance.tools:
                    # Replicas of one generation declare the same tools.
                    ready.setdefault(
                        (instance.module_id, instance.contract_major), instance
                    )
            if not after:
                break
        else:
            raise RemoteToolDirectoryError("discovery lists more instances than read")
        # One generation per module: the highest contract serving now.
        newest: dict[str, ModuleInstance] = {}
        for (module_id, major), instance in sorted(ready.items()):
            newest[module_id] = instance
        return [
            RemoteModuleTools(module_id, instance.contract_major, definitions)
            for module_id, instance in sorted(newest.items())
            if (definitions := _definitions(instance))
        ]

    # ---------------------------------------------------------------- invoker
    def invoke(
        self,
        definition: ToolDefinition,
        contract_major: int,
        arguments: Mapping[str, Any],
        config: Mapping[str, Any],
        context: ToolContext,
    ) -> Any:
        request = self._request(definition, arguments, config, context)
        return nats_runtime.run_coro(
            self._call(definition, contract_major, request),
            timeout=self.call_timeout_seconds + DISCOVERY_TIMEOUT_SECONDS + 5,
        )

    async def ainvoke(
        self,
        definition: ToolDefinition,
        contract_major: int,
        arguments: Mapping[str, Any],
        config: Mapping[str, Any],
        context: ToolContext,
    ) -> Any:
        request = self._request(definition, arguments, config, context)
        return await nats_runtime.run_coro_async(
            self._call(definition, contract_major, request),
            timeout=self.call_timeout_seconds + DISCOVERY_TIMEOUT_SECONDS + 5,
        )

    @staticmethod
    def _request(
        definition: ToolDefinition,
        arguments: Mapping[str, Any],
        config: Mapping[str, Any],
        context: ToolContext,
    ) -> pb.InvokeToolRequest:
        try:
            arguments_json = json.dumps(dict(arguments), allow_nan=False).encode()
            config_json = (
                json.dumps(dict(config), allow_nan=False).encode() if config else b""
            )
        except (TypeError, ValueError) as exc:
            raise RemoteToolError(
                "INVALID_ARGUMENT", "Arguments and configuration must be JSON"
            ) from exc
        if (
            len(arguments_json) > MAX_ARGUMENTS_BYTES
            or len(config_json) > MAX_CONFIG_BYTES
        ):
            raise RemoteToolError("PAYLOAD_TOO_LARGE", "Tool arguments are too large")
        request = pb.InvokeToolRequest(
            tool=definition.name,
            version=definition.version,
            arguments_json=arguments_json,
            config_json=config_json,
        )
        request.context.principal_id = context.user_id or ""
        request.context.workspace_id = context.workspace_id or ""
        return request

    async def _call(
        self,
        definition: ToolDefinition,
        contract_major: int,
        request: pb.InvokeToolRequest,
    ) -> Any:
        discovery, transport = self._clients()
        try:
            instances = await discovery.get_module(definition.module, contract_major)
            eligible = [
                instance
                for instance in instances
                if instance.status == "READY"
                and any(
                    tool.name == definition.name and tool.version == definition.version
                    for tool in instance.tools
                )
            ]
            if not eligible:
                raise RemoteToolError(
                    "MODULE_UNAVAILABLE",
                    f"No ready instance of '{definition.module}' serves {definition.id}",
                )
            target = random.choice(eligible)
            response = await ModuleToolClient(
                transport,
                tool_subject(self.project, target.instance_id, definition.name),
                target.instance_id,
            ).invoke(request)
        except RemoteToolError:
            raise
        except RPCError as exc:
            if exc.code in ("MODULE_NOT_FOUND", "INCOMPATIBLE_MODULE"):
                # Discovery knows no ready instance of that generation.
                raise RemoteToolError(
                    "MODULE_UNAVAILABLE",
                    f"No ready instance of '{definition.module}' serves {definition.id}",
                ) from exc
            raise RemoteToolError(exc.code, _reason(exc)) from exc
        except NoRespondersError as exc:
            raise RemoteToolError(
                "MODULE_UNAVAILABLE", f"'{definition.module}' did not take the call"
            ) from exc
        except TimeoutError as exc:
            raise RemoteToolError(
                "DEADLINE_EXCEEDED",
                f"'{definition.module}' did not answer in time: the tool may still have run",
            ) from exc
        except (NATSError, OSError) as exc:
            raise RemoteToolError("UNAVAILABLE", f"NATS failed: {exc}") from exc
        # Only the parse below is about the result: a ValueError above (a bad token
        # source, an identity) is not.
        try:
            return json.loads(response.result_json)
        except ValueError as exc:
            raise RemoteToolError(
                "TOOL_ERROR", "The tool's result is not JSON"
            ) from exc

    def close(self) -> None:
        with self._lock:
            discovery, tools = self._discovery, self._tools
            self._discovery = self._tools = None
        for transport in (discovery.transport if discovery else None, tools):
            if transport is None:
                continue
            try:
                nats_runtime.run_coro(transport.close(), timeout=5.0)
            except Exception as exc:  # noqa: BLE001 - close the other one too
                logger.debug(f"Remote tools: error closing a transport: {exc}")


def _reason(exc: RPCError) -> str:
    # What a module says is data for the model to read, not for the engine to trust.
    return str(exc).removeprefix(f"{exc.code}: ")[:MAX_ERROR_CHARACTERS]
