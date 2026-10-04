"""Data held by kernel services, as a platform super admin browses and edits it.

Each service exposes its data as a tree of entries (``""`` is the root):
containers hold entries, items hold a value. A ``ServiceResources`` adapter maps
one engine service onto that tree using only the service's public API, and says
what it can do (``ResourceCapabilities``, ``ResourceEntry.actions``). Changes
and reveals go through ``ResourceAdminService`` (``resources_service.py``), which
requires typed confirmation for destructive changes and audits every one in
``AdminAuditLog`` before it runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

# Bounded previews: a detail view never loads a whole object.
PREVIEW_BYTES = 64 * 1024


class ResourceNotFound(Exception):
    def __init__(self, service: str, resource_id: str) -> None:
        super().__init__(f"{service}: {resource_id!r} not found")
        self.service = service
        self.resource_id = resource_id


class UnsupportedOperation(Exception):
    """The service's public API cannot do this (e.g. list the keys of a cache)."""

    def __init__(self, service: str, operation: str) -> None:
        super().__init__(f"{service} does not support {operation}")
        self.service = service
        self.operation = operation


class InvalidResource(Exception):
    """A malformed id, or content the service cannot store."""

    def __init__(self, service: str, reason: str) -> None:
        super().__init__(f"{service}: {reason}")
        self.service = service
        self.reason = reason


class ResourceTooLarge(Exception):
    def __init__(self, service: str, resource_id: str, size: int, limit: int) -> None:
        super().__init__(f"{service}: {resource_id!r} is {size} bytes, over {limit}")
        self.service = service
        self.resource_id = resource_id
        self.size = size
        self.limit = limit


class UnknownService(Exception):
    def __init__(self, service: str) -> None:
        super().__init__(f"No data browser for service {service!r}")
        self.service = service


class ConfirmationRequired(Exception):
    """A destructive change needs the resource id typed back as ``confirm``."""

    def __init__(self, service: str, resource_id: str, operation: str) -> None:
        super().__init__(f"{operation} of {service} {resource_id!r} needs confirmation")
        self.service = service
        self.resource_id = resource_id
        self.operation = operation


class AuditUnavailable(Exception):
    """The audit record could not be written, so the change was not made."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"audit log unavailable: {reason}")
        self.reason = reason


Kind = Literal["container", "item"]
# What an entry allows; the web shows exactly these.
Action = Literal["read", "download", "write", "delete", "reveal"]


@dataclass(frozen=True)
class ResourceCapabilities:
    """What a service's data browser can do overall."""

    browse: bool = False  # entries can be listed under a parent
    lookup: bool = False  # some containers cannot list; their entries open by exact id
    create: bool = False  # new items can be written by id
    reveal: bool = False  # values are masked; one can be revealed (audited)
    # What a written value must be (shown by the editor), e.g. "JSON object", "Turtle".
    write_format: str = ""
    # list() filters by ``query`` on the server; otherwise the web filters loaded pages.
    search: bool = False
    # Items can be written with an expiry: write() takes ``ttl_seconds``.
    expiry: bool = False


@dataclass(frozen=True)
class ResourceEntry:
    id: str
    name: str
    kind: Kind
    actions: tuple[Action, ...] = ()
    size: int | None = None
    modified: str | None = None  # ISO 8601
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ResourcePage:
    parent: str
    entries: tuple[ResourceEntry, ...]
    next_cursor: str | None = None
    # False when the service cannot enumerate this container: open entries by id.
    listable: bool = True


@dataclass(frozen=True)
class ResourceContent:
    """An item's value, bounded to ``PREVIEW_BYTES``; ``masked`` carries no value."""

    encoding: Literal["text", "binary", "masked"]
    text: str | None = None
    size: int | None = None
    truncated: bool = False


@dataclass(frozen=True)
class ResourceDetail:
    """An entry, a bounded text preview, and optionally a structured ``view`` the
    web renders richly. ``view["type"]`` names its shape:

    - ``json``: ``{"value": any}``
    - ``table``: ``{"columns": [{"name", "type"}], "rows": [[...]], "total": int | None}``
    - ``triples``: ``{"triples": [[s, p, o]], "prefixes": {prefix: iri}, "total": int | None}``,
      each term in N-Triples syntax (``<iri>``, ``"text"@en``, ``"1"^^<datatype>``, ``_:b0``)
    - ``vector``: ``{"dimension": int, "components": [float], "norm": float | None}`` plus
      ``metadata`` / ``payload``
    - ``email``: ``{"from", "to", "cc", "subject", "text", "html", "sent_at"}``
    - ``message``: ``{"subject", "headers": {..}, "sequence", "published_at"}``
    - ``status``: ``{"phase", "fields": {label: value}}``
    - ``checkpoint``: a LangGraph checkpoint: ``agent_id``, ``thread_id``,
      ``checkpoint_ns``, ``checkpoint_id``, ``parent_id``, ``parent_entry`` (the
      previous step's entry id), ``created_at``, ``step``, ``source``, ``messages``
      (``{"role", "content", "name", "tool_calls": [{"id", "name", "args"}],
      "tool_call_id", "usage", "model"}``), ``channels`` (the other state),
      ``metadata`` and ``writes`` (``{"task_id", "task_path", "channel", "index",
      "value"}``); objects are ``{"$type": "module.Class", ...}``

    Never put a masked value in ``view``.
    """

    entry: ResourceEntry
    content: ResourceContent | None = None
    view: dict[str, Any] | None = None


class ServiceResources(Protocol):
    """One service's data. Every method raises ResourceNotFound,
    UnsupportedOperation, InvalidResource or SourceUnavailable.

    Listing entries may carry ``attributes["summary"]``: one short line the web
    shows under the name (a document's first fields, an event's payload...)."""

    service: str
    capabilities: ResourceCapabilities

    async def list(
        self, parent: str = "", *, cursor: str | None = None, limit: int = 100, **options: Any
    ) -> ResourcePage:
        """Entries directly under ``parent``, in a stable order; ``next_cursor`` pages.
        With ``capabilities.search``, ``query=`` keeps entries whose name contains it
        (case-insensitive)."""
        ...

    async def stat(self, resource_id: str) -> ResourceEntry:
        """The entry alone, without loading its value."""
        ...

    async def read(self, resource_id: str, *, reveal: bool = False) -> ResourceDetail:
        """The entry and a bounded preview; masked unless ``reveal``."""
        ...

    async def download(self, resource_id: str, *, max_bytes: int) -> bytes:
        """The whole value; ResourceTooLarge above ``max_bytes``."""
        ...

    async def write(self, resource_id: str, content: bytes) -> ResourceEntry:
        """Create or replace an item."""
        ...

    async def delete(self, resource_id: str) -> None: ...


class ExpiringResources(ServiceResources, Protocol):
    """A service with ``capabilities.expiry``: items can be written to expire."""

    async def write(
        self, resource_id: str, content: bytes, *, ttl_seconds: int | None = None
    ) -> ResourceEntry:
        """Create or replace an item, expiring ``ttl_seconds`` later when given."""
        ...


# --- audit -----------------------------------------------------------------------------


@dataclass(frozen=True)
class AdminAction:
    actor_id: str
    service: str
    operation: Literal["create", "replace", "delete", "reveal", "trigger", "cancel"]
    resource_id: str


Phase = Literal["requested", "succeeded", "failed"]


@dataclass(frozen=True)
class AuditRecord:
    action: AdminAction
    phase: Phase
    error: str = ""


@dataclass(frozen=True)
class AuditEntry:
    """A stored audit record, newest first in ``history``."""

    at: str  # ISO 8601
    actor_id: str
    actor: str  # display name or email when known, else the id
    service: str
    operation: str
    resource_id: str
    phase: str
    error: str = ""


class AdminAuditLog(Protocol):
    async def record(self, record: AuditRecord) -> None:
        """Persist ``record``; raises AuditUnavailable when it cannot."""
        ...

    async def history(
        self, *, service: str | None = None, resource_id: str | None = None, limit: int = 50
    ) -> list[AuditEntry]:
        """System app actions, newest first, optionally for one service or resource."""
        ...


# --- views -----------------------------------------------------------------------------


@dataclass(frozen=True)
class ResourceServiceInfo:
    name: str
    available: bool
    reason: str = ""
    capabilities: ResourceCapabilities = field(default_factory=ResourceCapabilities)


def paginate(
    parent: str, entries: list[ResourceEntry], cursor: str | None, limit: int
) -> ResourcePage:
    """One page of an already sorted listing. The cursor is the next offset."""
    try:
        start = int(cursor) if cursor else 0
    except ValueError as exc:
        raise InvalidResource("listing", f"bad cursor {cursor!r}") from exc
    if start < 0 or limit < 1:
        raise InvalidResource("listing", "cursor and limit must be positive")
    end = start + limit
    return ResourcePage(
        parent=parent,
        entries=tuple(entries[start:end]),
        next_cursor=str(end) if end < len(entries) else None,
    )


def text_preview(raw: bytes, total: int | None = None) -> ResourceContent:
    """UTF-8 text when ``raw`` decodes cleanly, else ``binary`` with no value.

    ``raw`` may be the first bytes of a larger value (``total``); a character cut
    by the preview boundary is dropped, not treated as binary.
    """
    size = len(raw) if total is None else total
    truncated = size > PREVIEW_BYTES or len(raw) > PREVIEW_BYTES
    head = raw[:PREVIEW_BYTES]
    try:
        text = head.decode("utf-8")
    except UnicodeDecodeError as exc:
        cut_at_boundary = truncated and exc.start >= len(head) - 3
        if not cut_at_boundary:
            return ResourceContent("binary", size=size, truncated=truncated)
        text = head[: exc.start].decode("utf-8")
    if "\x00" in text:
        return ResourceContent("binary", size=size, truncated=truncated)
    return ResourceContent("text", text=text, size=size, truncated=truncated)
