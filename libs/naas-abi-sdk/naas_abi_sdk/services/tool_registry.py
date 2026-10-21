"""Read the engine's tool catalog: list, get and search. Nothing here runs a tool.

What a module sees is decided by the engine from the module's identity, never
by the request. A tool is found by ``tool_id`` (``<namespace>/<name>@<version>``);
credentials are never part of a definition: a config requirement names a key
(``secret=True`` for a credential) and ``availability`` says which keys the engine
still lacks.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from naas_abi_proto.tool_registry.v1 import tool_registry_pb2 as pb

from naas_abi_sdk.services.errors import domain_error
from naas_abi_sdk.tool_registry import ToolRegistryClient
from naas_abi_sdk.transport import RPCError

MAX_LIST_PAGES = 100


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

    @staticmethod
    async def _call(call):
        try:
            return await call
        except RPCError as exc:
            raise domain_error(exc) from exc
