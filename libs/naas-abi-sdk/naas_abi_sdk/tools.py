"""Tools a module serves, and the client that calls one (abi.tool.v1).

A module declares ``ToolDescriptor``s and binds a handler to each with
``expose_tool``; discovery stores the descriptors as the portable
``abi.tool_registry.v1.ToolDefinition``, and ``ToolHost`` serves the calls
(``tool_host.py``). Stdlib and proto only: importable without the host's
optional ``jsonschema``.

A tool's arguments and result are JSON, never a pickle or a callable. Nothing
here carries an engine secret: a tool takes the plain configuration values its
descriptor names, and the module holds its own credentials.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from naas_abi_proto.tool.v1 import tool_pb2 as pb
from naas_abi_proto.tool_registry.v1 import tool_registry_pb2 as definition_pb

# Where the engine's own processes may call tools from, and which of them speak for
# an end user (the same rule as apps: docs/adr/20261014_module-identities.md).
ENGINE_CALLERS = frozenset({"api", "engine", "dagster"})
USER_CALLERS = frozenset({"api", "engine"})

MAX_REQUEST_BYTES = 512 * 1024
MAX_ARGUMENTS_BYTES = 256 * 1024
MAX_CONFIG_BYTES = 64 * 1024
MAX_RESULT_BYTES = 512 * 1024
DEFAULT_DEADLINE_SECONDS = 60.0
MAX_DEADLINE_SECONDS = 300.0
MAX_ERROR_CHARACTERS = 1024
# Running an engine tool (abi.svc.tool_registry.v1.InvokeToolRequest): `secret_refs` maps a
# configuration key to the name of an engine secret.
MAX_SECRET_REFS = 16
MAX_SECRET_NAME_CHARS = 128
SECRET_NAME = r"[A-Za-z_][A-Za-z0-9_]*"

_NAME = re.compile(r"[A-Za-z0-9_-]{1,64}")
_VERSION = re.compile(r"\d+(?:\.\d+){0,2}")
_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def tool_subject(project: str, instance_id: str, name: str) -> str:
    return f"abi.mod.{project}.{instance_id}.tool.{name}.invoke"


class ToolError(Exception):
    """A failure the handler reports to its caller, message included.

    Any other exception is logged in the module and reported as a generic
    ``TOOL_ERROR``: a handler's internals never travel to the caller."""


@dataclass(frozen=True)
class ToolConfig:
    """A non-secret configuration value a tool takes from the record that binds it."""

    key: str
    description: str = ""
    required: bool = True

    def __post_init__(self) -> None:
        if not _KEY.fullmatch(self.key):
            raise ValueError(f"Invalid tool configuration key: {self.key!r}")


@dataclass(frozen=True)
class ToolDescriptor:
    """A tool this module serves: what an agent finds, enables and calls.

    ``input_schema`` is a JSON Schema object the module validates every call's
    arguments against before the handler runs. Replicas must declare the same
    tools, and a name carries one version.
    """

    name: str
    description: str
    input_schema: Mapping[str, Any] = field(
        default_factory=lambda: {"type": "object", "properties": {}}
    )
    version: str = "1"
    output_schema: Mapping[str, Any] | None = None
    tags: tuple[str, ...] = ()
    config: tuple[ToolConfig, ...] = ()
    required_scopes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not _NAME.fullmatch(self.name):
            raise ValueError(f"Invalid tool name: {self.name!r}")
        if not _VERSION.fullmatch(self.version):
            raise ValueError(f"Invalid tool version: {self.version!r}")
        if not self.description.strip():
            raise ValueError("A tool needs a description: search ranks on it")
        if self.input_schema.get("type", "object") != "object":
            raise ValueError("A tool's input schema describes an object")

    def to_pb(self, module_id: str) -> definition_pb.ToolDefinition:
        """The definition discovery stores, canonical so replicas compare equal."""
        return definition_pb.ToolDefinition(
            id=f"{module_id}/{self.name}@{self.version}",
            namespace=module_id,
            name=self.name,
            version=self.version,
            module=module_id,
            description=self.description,
            input_schema_json=_canonical(self.input_schema),
            output_schema_json=(
                _canonical(self.output_schema)
                if self.output_schema is not None
                else b""
            ),
            tags=self.tags,
            requirements=definition_pb.ToolRequirements(
                config=[
                    definition_pb.ConfigRequirement(
                        key=c.key, description=c.description, required=c.required
                    )
                    for c in self.config
                ]
            ),
            required_scopes=self.required_scopes,
        )

    @classmethod
    def from_pb(cls, value: definition_pb.ToolDefinition) -> ToolDescriptor:
        return cls(
            name=value.name,
            description=value.description,
            input_schema=json.loads(value.input_schema_json or b"{}"),
            version=value.version,
            output_schema=(
                json.loads(value.output_schema_json)
                if value.output_schema_json
                else None
            ),
            tags=tuple(value.tags),
            config=tuple(
                ToolConfig(c.key, c.description, c.required)
                for c in value.requirements.config
            ),
            required_scopes=tuple(value.required_scopes),
        )


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


@dataclass(frozen=True)
class ToolCaller:
    """Who calls: the service identity discovery verified, and the end user they
    speak for (only the engine's own processes may name one)."""

    identity: str
    admin: bool = False
    user_id: str | None = None
    workspace_id: str | None = None

    @property
    def engine(self) -> bool:
        return self.identity in ENGINE_CALLERS


@dataclass(frozen=True)
class ToolCall:
    """What a handler may ask for besides the arguments: declare ``call`` (or
    ``**kwargs``) in its signature."""

    tool: str
    caller: ToolCaller
    config: Mapping[str, Any]
    trace_id: str = ""


class ModuleToolClient:
    """Unary invoke client for one tool on one module instance."""

    def __init__(self, transport: Any, subject: str, instance_id: str) -> None:
        self._transport, self.subject, self.instance_id = (
            transport,
            subject,
            instance_id,
        )

    async def invoke(
        self, request: pb.InvokeToolRequest, *, timeout: float | None = None
    ) -> pb.InvokeToolResponse:
        """``timeout``: how long to wait, and the handler's deadline (the host reads
        it from ``context.timeout_ms``); default the transport's."""
        kwargs = {} if timeout is None else {"timeout": timeout}
        return await self._transport.call(
            self.subject,
            request,
            pb.InvokeToolResponse,
            instance_id=self.instance_id,
            **kwargs,
        )
