"""Ports, DTOs and exceptions for the tool registry.

The registry is the process-wide catalog of capabilities that modules publish
and that agents consume. It holds two things per tool:

* a **definition**: a serialisable description of the operation (stable id,
  description, input/output contracts, owning module, configuration
  requirements, visibility). Definitions are what records reference, what
  semantic search indexes, and what can cross a process boundary.
* a **binding**: a runtime factory that turns a definition into an executable
  tool for a given caller context and configuration. Bindings never leave the
  process, and records never contain them.

The domain is technology agnostic: an executable tool is an opaque ``object``
here. The LangChain adapters in ``adapters/primary`` produce ``BaseTool``
instances, and the agent runtime consumes them as such.

Tool ids are ``<namespace>/<name>@<version>``:

* ``namespace``: the publishing module's dotted import path
  (e.g. ``naas_abi_marketplace.applications.github``).
* ``name``: the model-facing tool name, unique within the namespace.
* ``version``: ``MAJOR[.MINOR[.PATCH]]``. Bump the major version when the
  input contract changes incompatibly.

A *reference* (``ToolRef``) may omit the version, in which case it resolves to
the highest published version.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator

NAMESPACE_PATTERN = r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*"
NAME_PATTERN = r"[A-Za-z0-9_-]{1,64}"
VERSION_PATTERN = r"\d+(?:\.\d+){0,2}"

_REF_RE = re.compile(
    rf"^(?P<namespace>{NAMESPACE_PATTERN})/(?P<name>{NAME_PATTERN})"
    rf"(?:@(?P<version>{VERSION_PATTERN}))?$"
)


# --------------------------------------------------------------------------- #
# Exceptions                                                                   #
# --------------------------------------------------------------------------- #


class ToolRegistryError(Exception):
    """Base class for every tool registry failure."""


class InvalidToolReferenceError(ToolRegistryError, ValueError):
    """A tool id or reference string is malformed."""


class ToolNotFoundError(ToolRegistryError, LookupError):
    """No published tool matches the reference."""


class ToolAlreadyPublishedError(ToolRegistryError):
    """Another module already published a tool with the same id."""


class ToolAccessDeniedError(ToolRegistryError, PermissionError):
    """The caller context is not allowed to perform the action on the tool."""


class ToolConfigurationError(ToolRegistryError):
    """Required configuration is missing, so the tool cannot be resolved."""

    def __init__(self, tool_id: str, missing: Sequence[str]):
        self.tool_id = tool_id
        self.missing = tuple(missing)
        super().__init__(
            f"Tool '{tool_id}' is missing required configuration: "
            f"{', '.join(self.missing)}. Provide it in the tool binding's "
            "'config' (use a secret reference for credentials) or configure "
            "the publishing module."
        )


class ToolResolutionError(ToolRegistryError):
    """The binding failed to build an executable tool."""


class ToolSearchUnavailableError(ToolRegistryError):
    """Semantic search needs an embedder and an index, and one is missing."""


# --------------------------------------------------------------------------- #
# Identifiers                                                                  #
# --------------------------------------------------------------------------- #


def _version_key(version: str) -> tuple[int, int, int]:
    parts = [int(part) for part in version.split(".")]
    while len(parts) < 3:
        parts.append(0)
    return (parts[0], parts[1], parts[2])


class ToolRef(BaseModel):
    """A reference to a tool, with an optional version."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    namespace: str = Field(pattern=f"^{NAMESPACE_PATTERN}$")
    name: str = Field(pattern=f"^{NAME_PATTERN}$")
    version: str | None = Field(default=None, pattern=f"^{VERSION_PATTERN}$")

    @classmethod
    def parse(cls, raw: str) -> ToolRef:
        match = _REF_RE.match(raw.strip()) if isinstance(raw, str) else None
        if match is None:
            raise InvalidToolReferenceError(
                f"Invalid tool reference {raw!r}: expected "
                "'<namespace>/<name>' or '<namespace>/<name>@<version>', e.g. "
                "'naas_abi_marketplace.applications.github/create_issue@1'."
            )
        return cls(**match.groupdict())

    def matches(self, tool_id: ToolId) -> bool:
        return (
            self.namespace == tool_id.namespace
            and self.name == tool_id.name
            and (self.version is None or self.version == tool_id.version)
        )

    def __str__(self) -> str:
        base = f"{self.namespace}/{self.name}"
        return f"{base}@{self.version}" if self.version else base


class ToolId(BaseModel):
    """The stable, fully qualified identifier of a published tool."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    namespace: str = Field(pattern=f"^{NAMESPACE_PATTERN}$")
    name: str = Field(pattern=f"^{NAME_PATTERN}$")
    version: str = Field(pattern=f"^{VERSION_PATTERN}$")

    @classmethod
    def parse(cls, raw: str) -> ToolId:
        ref = ToolRef.parse(raw)
        if ref.version is None:
            raise InvalidToolReferenceError(
                f"Tool id {raw!r} has no version; a tool id is "
                "'<namespace>/<name>@<version>'."
            )
        return cls(namespace=ref.namespace, name=ref.name, version=ref.version)

    @property
    def version_key(self) -> tuple[int, int, int]:
        return _version_key(self.version)

    def __str__(self) -> str:
        return f"{self.namespace}/{self.name}@{self.version}"


# --------------------------------------------------------------------------- #
# Definitions                                                                  #
# --------------------------------------------------------------------------- #


class ConfigRequirement(BaseModel):
    """One configuration value a tool needs to be resolved."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    description: str = ""
    secret: bool = False
    required: bool = True


class ToolRequirements(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    config: tuple[ConfigRequirement, ...] = ()
    # The tool only works when a coding workspace is bound to the request.
    requires_workspace: bool = False


class ToolDefinition(BaseModel):
    """Serialisable description of a published tool."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    namespace: str = Field(pattern=f"^{NAMESPACE_PATTERN}$")
    name: str = Field(pattern=f"^{NAME_PATTERN}$")
    version: str = Field(default="1", pattern=f"^{VERSION_PATTERN}$")
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] | None = None
    module: str
    tags: tuple[str, ...] = ()
    requirements: ToolRequirements = ToolRequirements()
    # Caller must hold every one of these scopes to discover, enable or run it.
    required_scopes: tuple[str, ...] = ()

    @property
    def id(self) -> ToolId:
        return ToolId(namespace=self.namespace, name=self.name, version=self.version)

    def required_config_keys(self) -> tuple[str, ...]:
        return tuple(r.key for r in self.requirements.config if r.required)

    def embedding_text(self) -> str:
        """The text semantic search embeds for this definition.

        It covers everything a capability request can paraphrase: the name
        split into words, the description, the parameters and the tags. Any
        change to it changes the index fingerprint and triggers re-embedding.
        """
        lines = [
            self.name.replace("_", " ").replace("-", " "),
            self.description.strip(),
        ]
        properties = self.input_schema.get("properties", {})
        if isinstance(properties, dict) and properties:
            params = []
            for key, spec in properties.items():
                description = (
                    spec.get("description") if isinstance(spec, dict) else None
                )
                params.append(f"{key}: {description}" if description else key)
            lines.append("parameters: " + "; ".join(params))
        if self.tags:
            lines.append("tags: " + ", ".join(self.tags))
        # The last segment names the product ("github"); the package path
        # before it is shared by every marketplace tool and only adds noise.
        lines.append(f"module: {self.module.rsplit('.', 1)[-1].replace('_', ' ')}")
        return "\n".join(line for line in lines if line)


# --------------------------------------------------------------------------- #
# Caller context and results                                                   #
# --------------------------------------------------------------------------- #


class ToolContext(BaseModel):
    """Who is asking, and in which scope. Drives visibility and authorization."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    user_id: str | None = None
    workspace_id: str | None = None
    scopes: frozenset[str] = frozenset()

    @field_validator("scopes", mode="before")
    @classmethod
    def _normalise_scopes(cls, value: Any) -> frozenset[str]:
        if value is None:
            return frozenset()
        return frozenset(value)


class ToolAction(StrEnum):
    DISCOVER = "discover"
    ENABLE = "enable"
    EXECUTE = "execute"


class ToolAvailability(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    available: bool
    missing_config: tuple[str, ...] = ()


class ToolSearchResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_id: str
    name: str
    description: str
    module: str
    score: float
    availability: ToolAvailability
    definition: ToolDefinition


# --------------------------------------------------------------------------- #
# Bindings                                                                     #
# --------------------------------------------------------------------------- #


@runtime_checkable
class ToolBinding(Protocol):
    """Runtime factory for one published tool.

    ``default_config`` holds values the publishing module already knows (for
    example its configured access token). It is never exposed through a
    definition or a search result.
    """

    @property
    def default_config(self) -> Mapping[str, Any]: ...

    def create(self, context: ToolContext, config: Mapping[str, Any]) -> object: ...


@dataclass(frozen=True)
class PublishedTool:
    definition: ToolDefinition
    binding: ToolBinding


# --------------------------------------------------------------------------- #
# Secondary ports                                                              #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ToolIndexEntry:
    id: str
    fingerprint: str
    vector: tuple[float, ...]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolIndexHit:
    id: str
    score: float


class IToolIndexPort(ABC):
    """Vector index over tool definitions. Owned by the registry.

    ``prepare`` binds the index to an embedding model. Vectors from different
    models are not comparable, so preparing with a new ``model_key`` discards
    everything indexed under the previous one. Storage is created lazily on
    the first ``upsert``, sized from its vectors.
    """

    @abstractmethod
    def prepare(self, model_key: str) -> None: ...

    @abstractmethod
    def fingerprints(self, ids: Sequence[str]) -> dict[str, str]:
        """Return the stored fingerprint of every id in ``ids`` that is indexed."""

    @abstractmethod
    def upsert(self, entries: Sequence[ToolIndexEntry]) -> None: ...

    @abstractmethod
    def delete(self, ids: Sequence[str]) -> None: ...

    @abstractmethod
    def search(self, vector: Sequence[float], limit: int) -> list[ToolIndexHit]:
        """Most similar first. ``limit`` must be positive."""

    @abstractmethod
    def size(self) -> int: ...


class IToolEmbedderPort(ABC):
    """Turns text into vectors for tool search."""

    @property
    @abstractmethod
    def model_key(self) -> str:
        """Identifies the embedding model; a change invalidates the index."""

    @abstractmethod
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    @abstractmethod
    def embed_query(self, text: str) -> list[float]: ...


class IToolAccessPolicy(ABC):
    """Decides whether a caller may discover, enable or execute a tool."""

    @abstractmethod
    def check(
        self, definition: ToolDefinition, context: ToolContext, action: ToolAction
    ) -> None:
        """Return normally when allowed; raise ``ToolAccessDeniedError`` otherwise."""


# --------------------------------------------------------------------------- #
# Primary port                                                                 #
# --------------------------------------------------------------------------- #


class IToolRegistry(ABC):
    # ------------------------------------------------------------ publication
    @abstractmethod
    def publish(self, module: str, tools: Sequence[PublishedTool]) -> None:
        """Replace every tool ``module`` published before with ``tools``."""

    @abstractmethod
    def unpublish(self, module: str) -> None: ...

    # ---------------------------------------------------------------- lookup
    @abstractmethod
    def get_definition(self, ref: str | ToolRef | ToolId) -> ToolDefinition:
        """Raise ``ToolNotFoundError`` when nothing matches."""

    @abstractmethod
    def list_definitions(
        self, context: ToolContext | None = None
    ) -> list[ToolDefinition]:
        """Every definition the context may discover. ``None`` lists them all."""

    @abstractmethod
    def availability(
        self, ref: str | ToolRef | ToolId, config: Mapping[str, Any] | None = None
    ) -> ToolAvailability: ...

    # ------------------------------------------------------------ resolution
    @abstractmethod
    def check_access(
        self,
        ref: str | ToolRef | ToolId,
        context: ToolContext,
        action: ToolAction,
    ) -> ToolDefinition: ...

    @abstractmethod
    def resolve(
        self,
        ref: str | ToolRef | ToolId,
        context: ToolContext,
        config: Mapping[str, Any] | None = None,
        action: ToolAction = ToolAction.EXECUTE,
    ) -> object:
        """Build an executable tool, enforcing access and configuration."""

    # ---------------------------------------------------------------- search
    @abstractmethod
    def search_tools(
        self,
        query: str,
        context: ToolContext | None = None,
        limit: int = 5,
        min_score: float | None = None,
        where: Callable[[ToolDefinition], bool] | None = None,
    ) -> list[ToolSearchResult]:
        """Semantic search. Never executes nor grants access to a tool.

        ``where`` narrows the candidates further (e.g. an agent's allow list).
        It is applied before ``limit``, so filtered-out hits never starve it.
        """

    @abstractmethod
    def sync_index(self) -> int:
        """Bring the index in line with the published definitions.

        Returns how many definitions were (re-)embedded.
        """
