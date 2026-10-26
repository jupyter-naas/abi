"""Read the engine's tool catalog (list, get, search) and run its tools (``invoke``).

What a module sees and runs is decided by the engine from the module's identity,
never by the request. A tool is found by ``tool_id`` (``<namespace>/<name>@<version>``);
credentials are never part of a definition: a config requirement names a key
(``secret=True`` for a credential) and ``availability`` says which keys the engine
still lacks.

``invoke`` runs an engine tool *on the engine*: the tool, its configuration and the
secrets it reads never reach this process. A credential is passed by the NAME of an
engine secret (``secrets={"access_token": "GITHUB_ACCESS_TOKEN"}``), which the engine
resolves only when it allows this module that name; writing a credential's value is
refused. ``as_tool`` wraps one as a LangChain tool (``naas_abi_sdk.engine_tools``,
extra ``engine-tools``) so an SDK agent can bind what it found by search.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from naas_abi_proto.tool_registry.v1 import tool_registry_pb2 as pb

from naas_abi_sdk.cancellation import new_call_id
from naas_abi_sdk.tools import (
    DEFAULT_DEADLINE_SECONDS,
    MAX_ARGUMENTS_BYTES,
    MAX_CONFIG_BYTES,
    MAX_DEADLINE_SECONDS,
    MAX_SECRET_REFS,
)
from naas_abi_sdk.services.errors import (
    ToolExecutionError,
    ToolPermissionDenied,
    domain_error,
)
from naas_abi_sdk.tool_registry import ToolRegistryClient
from naas_abi_sdk.transport import RPCError

logger = logging.getLogger(__name__)

MAX_LIST_PAGES = 100
# How long a caller that gives up waits for the engine to take its cancel.
CANCEL_WAIT_SECONDS = 3.0
# What the engine accepts of a call is `naas_abi_sdk.tools`' (one place for the contract).
DEFAULT_INVOKE_TIMEOUT = DEFAULT_DEADLINE_SECONDS
MAX_INVOKE_TIMEOUT = MAX_DEADLINE_SECONDS
# The caller waits this long beyond the tool's deadline, so the engine's own
# DEADLINE_EXCEEDED reply is the one it reads.
INVOKE_GRACE_SECONDS = 5.0


@dataclass(frozen=True)
class ConfigRequirement:
    key: str
    description: str = ""
    secret: bool = False
    required: bool = True


@dataclass(frozen=True)
class ToolDefinition:
    id: str
    namespace: str
    name: str
    version: str
    module: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] | None = None
    tags: tuple[str, ...] = ()
    config: tuple[ConfigRequirement, ...] = ()
    requires_workspace: bool = False
    required_scopes: tuple[str, ...] = ()
    # Served by an SDK module (naas_abi_sdk.tools) rather than by the engine's own code.
    remote: bool = False


@dataclass(frozen=True)
class ToolAvailability:
    available: bool
    missing_config: tuple[str, ...] = ()


@dataclass(frozen=True)
class ToolEntry:
    definition: ToolDefinition
    availability: ToolAvailability


@dataclass(frozen=True)
class ToolMatch:
    definition: ToolDefinition
    availability: ToolAvailability
    score: float

    @property
    def tool_id(self) -> str:
        return self.definition.id


def _json_object(data: bytes) -> dict[str, Any]:
    return json.loads(data) if data else {}


def _definition(message: pb.ToolDefinition) -> ToolDefinition:
    return ToolDefinition(
        id=message.id,
        namespace=message.namespace,
        name=message.name,
        version=message.version,
        module=message.module,
        description=message.description,
        input_schema=_json_object(message.input_schema_json),
        output_schema=(
            _json_object(message.output_schema_json)
            if message.output_schema_json
            else None
        ),
        tags=tuple(message.tags),
        config=tuple(
            ConfigRequirement(r.key, r.description, r.secret, r.required)
            for r in message.requirements.config
        ),
        requires_workspace=message.requirements.requires_workspace,
        required_scopes=tuple(message.required_scopes),
        remote=message.remote,
    )


def _entry(message: pb.ToolEntry) -> ToolEntry:
    return ToolEntry(
        definition=_definition(message.definition),
        availability=ToolAvailability(
            message.availability.available, tuple(message.availability.missing_config)
        ),
    )


def _filter(
    modules: Sequence[str], tags: Sequence[str], available_only: bool
) -> pb.ToolFilter:
    if isinstance(modules, str) or isinstance(tags, str):
        raise TypeError("modules and tags are sequences of strings")
    return pb.ToolFilter(modules=modules, tags=tags, available_only=available_only)


class ToolRegistryService:
    def __init__(self, client: ToolRegistryClient) -> None:
        self._client = client

    async def list_tools(
        self,
        *,
        modules: Sequence[str] = (),
        tags: Sequence[str] = (),
        available_only: bool = False,
    ) -> list[ToolEntry]:
        """Every tool this module may discover, sorted by id.

        ``modules``: the tool's module is one of them. ``tags``: it has all of them.
        ``available_only``: leave out tools the engine cannot build yet.
        """
        filter = _filter(modules, tags, available_only)
        entries: list[ToolEntry] = []
        after = ""
        for _ in range(MAX_LIST_PAGES):
            page = await self._call(
                self._client.list_tools(
                    pb.ListToolsRequest(filter=filter, limit=200, after=after)
                )
            )
            entries.extend(_entry(tool) for tool in page.tools)
            if not page.next_after:
                return entries
            after = page.next_after
        raise RuntimeError("The tool catalog is too large to list")

    async def get_tool(self, ref: str) -> ToolEntry:
        """``<namespace>/<name>`` (the highest version) or ``<namespace>/<name>@<version>``.

        Raises ``ToolNotFound`` when no tool this module may discover matches.
        """
        response = await self._call(self._client.get_tool(pb.GetToolRequest(ref=ref)))
        return _entry(response.tool)

    async def search_tools(
        self,
        query: str,
        *,
        limit: int = 5,
        min_score: float | None = None,
        modules: Sequence[str] = (),
        tags: Sequence[str] = (),
        available_only: bool = False,
    ) -> list[ToolMatch]:
        """The tools that best fit ``query``, best first. At most 50.

        Raises ``ToolSearchUnavailable`` when the engine has no embedding model
        or index for tool search.
        """
        if not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")
        if min_score is not None and not math.isfinite(min_score):
            raise ValueError("min_score must be finite")
        request = pb.SearchToolsRequest(
            query=query, limit=limit, filter=_filter(modules, tags, available_only)
        )
        if min_score is not None:
            request.min_score = min_score
        response = await self._call(self._client.search_tools(request))
        matches = []
        for match in response.matches:
            entry = _entry(match.tool)
            matches.append(ToolMatch(entry.definition, entry.availability, match.score))
        return matches

    async def invoke(
        self,
        ref: str,
        arguments: Mapping[str, Any] | None = None,
        *,
        config: Mapping[str, Any] | None = None,
        secrets: Mapping[str, str] | None = None,
        version: str = "",
        timeout: float = DEFAULT_INVOKE_TIMEOUT,
    ) -> Any:
        """Run an engine tool on the engine; its JSON result.

        ``ref``: ``<namespace>/<name>`` (the highest version) or
        ``<namespace>/<name>@<version>``. ``arguments``: a JSON object the engine
        validates against the tool's input schema. ``config``: plain values for
        non-secret configuration keys. ``secrets``: configuration key (one the
        definition marks ``secret=True``) -> the NAME of an engine secret; the engine
        resolves it if it allows this module that name, and never sends the value back.
        ``timeout``: how long to wait, and the tool's deadline (at most 300 seconds).

        Raises ``ToolNotFound`` (no tool this module may discover matches),
        ``ToolPermissionDenied`` (a secret it may not use, a credential written inline,
        a tool it is not granted), ``ToolExecutionError`` (the tool failed) and
        ``ServiceError`` for the other codes (``INVALID_ARGUMENT``,
        ``PAYLOAD_TOO_LARGE``, ``RESOURCE_EXHAUSTED``, ``DEADLINE_EXCEEDED``). The
        caller waits ``timeout`` plus a few seconds, so the engine's
        ``DEADLINE_EXCEEDED`` is what a slow tool gives; a reply lost past that wait is
        a ``DEADLINE_EXCEEDED`` too (the tool may still have run).
        Nothing is retried: a tool may have side effects.

        Cancelling the task that awaits ``invoke`` (or a wait that runs out) tells the
        engine to stop the tool: a tool with a coroutine is cancelled at its next
        ``await``, a synchronous one is told and cannot be interrupted. The engine
        answers a cancelled call ``CANCELLED``; nobody reads it here.
        """
        if not isinstance(ref, str) or not ref:
            raise ValueError("ref is a tool reference")
        if not 0 < timeout <= MAX_INVOKE_TIMEOUT or not math.isfinite(timeout):
            raise ValueError(f"timeout must be between 0 and {MAX_INVOKE_TIMEOUT:g}")
        secrets = dict(secrets or {})
        if len(secrets) > MAX_SECRET_REFS:
            raise ValueError(f"At most {MAX_SECRET_REFS} secrets")
        if not all(
            isinstance(key, str) and isinstance(name, str)
            for key, name in secrets.items()
        ):
            raise TypeError("secrets maps a configuration key to a secret's name")
        try:
            encoded_arguments = json.dumps(
                dict(arguments or {}), allow_nan=False
            ).encode()
            encoded_config = (
                json.dumps(dict(config), allow_nan=False).encode() if config else b""
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("Arguments and config must be JSON values") from exc
        if len(encoded_arguments) > MAX_ARGUMENTS_BYTES:
            raise ValueError("Arguments exceed 256 KiB")
        if len(encoded_config) > MAX_CONFIG_BYTES:
            raise ValueError("Config exceeds 64 KiB")
        request = pb.InvokeToolRequest(
            tool=ref,
            version=version,
            arguments_json=encoded_arguments,
            config_json=encoded_config,
            secret_refs=secrets,
            call_id=new_call_id(),
        )
        try:
            response = await self._client.invoke_tool(
                request, timeout=timeout, grace=INVOKE_GRACE_SECONDS
            )
        except asyncio.CancelledError:
            # The caller gave up: the engine stops the tool it is running for it.
            await self._cancel_quietly(request.call_id)
            raise
        except asyncio.TimeoutError as exc:  # noqa: UP041 - not the builtin on Python 3.10
            await self._cancel_quietly(request.call_id)
            raise domain_error(
                RPCError(
                    "DEADLINE_EXCEEDED",
                    f"No reply from the engine within {timeout:g}s: the tool may still "
                    "have run",
                )
            ) from exc
        except RPCError as exc:
            if exc.code == "PERMISSION_DENIED":
                raise ToolPermissionDenied(
                    exc.code, str(exc), response=exc.response
                ) from exc
            if exc.code == "TOOL_ERROR":
                raise ToolExecutionError(
                    exc.code, str(exc), response=exc.response
                ) from exc
            raise domain_error(exc) from exc
        return json.loads(response.result_json)

    async def as_tool(
        self,
        tool: str | ToolDefinition | ToolMatch | ToolEntry,
        *,
        config: Mapping[str, Any] | None = None,
        secrets: Mapping[str, str] | None = None,
        timeout: float = DEFAULT_INVOKE_TIMEOUT,
        name: str | None = None,
    ) -> Any:
        """An engine tool as a LangChain tool whose calls ``invoke`` it.

        ``tool``: a reference (the definition is fetched), or what ``get_tool`` and
        ``search_tools`` returned. Needs the ``engine-tools`` extra. See
        ``naas_abi_sdk.engine_tools.engine_tool``."""
        from naas_abi_sdk.engine_tools import engine_tool

        if isinstance(tool, str):
            tool = await self.get_tool(tool)
        return engine_tool(
            self, tool, config=config, secrets=secrets, timeout=timeout, name=name
        )

    async def _cancel_quietly(self, call_id: str) -> None:
        # Shielded: the caller's own cancellation must not stop the cancel it sends.
        try:
            await asyncio.shield(
                asyncio.wait_for(
                    self._client.cancel_tool(pb.CancelToolRequest(call_id=call_id)),
                    CANCEL_WAIT_SECONDS,
                )
            )
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # noqa: BLE001 - the caller's exit comes first
            logger.debug("Engine tool cancel not delivered: %s", type(exc).__name__)

    @staticmethod
    async def _call(call):
        try:
            return await call
        except RPCError as exc:
            raise domain_error(exc) from exc
