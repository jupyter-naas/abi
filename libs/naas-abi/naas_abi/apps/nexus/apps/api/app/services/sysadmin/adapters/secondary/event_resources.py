"""The event log, read-only: event types are containers, events are items.

Wraps the engine's ``EventService`` (sync; calls run in a worker thread)
through its raw, IRI-based API (``event_types``, ``query_stored``,
``get_stored``), so every type can be read, including ones whose Python class
is not importable here. The log is append-only by design: nothing is written
or deleted from here.

Ids: a type is its class IRI, percent-encoded (``/`` and all); an event is
``<type id>/<seq>``. Events list newest first; the cursor is the last seq shown.

For a log explorer: a type is named in words ("Agent AI message emitted") with
its domain, count and last seen; an event carries a one-line ``summary`` of its
informative payload fields (boilerplate dropped, IRIs shortened), its actor and
what triggered it. Search is on the server: type names at the root, the raw
payload text within a type (``EventService.query_stored(search=...)``).
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any
from urllib.parse import quote, unquote

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    Action,
    InvalidResource,
    ResourceCapabilities,
    ResourceDetail,
    ResourceEntry,
    ResourceNotFound,
    ResourcePage,
    ResourceTooLarge,
    UnsupportedOperation,
    paginate,
    text_preview,
)
from naas_abi_core.services.event.EventPort import EventNotFoundError

SERVICE = "event"
EVENT_ACTIONS: tuple[Action, ...] = ("read", "download")

# Fields every LogProcess carries: identity and provenance plumbing, not news.
BOILERPLATE = frozenset(
    {
        "_uri",
        "_class_uri",
        "_property_uris",
        "label",
        "created",
        "creator",
        "created_at",
        "created_by",
        "occurs_in",
        "updates",
    }
)
# Most telling first; anything else follows, ids and plumbing last.
PRIORITY = (
    "event_name",
    "agent_name",
    "name",
    "path",
    "page_path",
    "graph_name",
    "topic",
    "routing_key",
    "changed_fields",
    "status",
    "content",
    "triple_count",
    "size_bytes",
    "chat_id",
)
LAST = ("actor_user_id", "user_id", "workspace_id", "actor_workspace_id", "target_workspace_id")
QUIET = frozenset(
    {"triggered_via", "session_id", "event_id", "timestamp", "payload_json", "changes_json"}
)
SUMMARY_FIELDS = 4
VALUE_CLIP = 48
WORD = re.compile(r"[A-Z]+(?=[A-Z][a-z]|\d|\b)|[A-Z]?[a-z]+|[A-Z]+|\d+")


def _type_id(event_type: str) -> str:
    return quote(event_type, safe="")


def _local_name(iri: str) -> str:
    return iri.rstrip("/#").rsplit("#", 1)[-1].rsplit("/", 1)[-1] or iri


def humanize(local: str) -> str:
    """``AgentAIMessageEmitted`` -> ``Agent AI message emitted``."""
    words = WORD.findall(local)
    if not words:
        return local
    shown = [w if (w.isupper() and len(w) > 1) else w.lower() for w in words]
    shown[0] = shown[0][:1].upper() + shown[0][1:]
    return " ".join(shown)


def domain(iri: str) -> str:
    """The path segment naming where a type comes from (``agent``, ``nexus``...)."""
    head = iri.rstrip("/#")
    head = head.rsplit("#", 1)[0] if "#" in head else head.rsplit("/", 1)[0]
    return head.rstrip("/").rsplit("/", 1)[-1]


def _short(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(_short(v) for v in value[:3]) + ("…" if len(value) > 3 else "")
    if isinstance(value, dict):
        return "{" + ", ".join(list(value)[:3]) + ("…}" if len(value) > 3 else "}")
    text = str(value).strip().replace("\n", " ")
    if text.startswith(("http://", "https://")):
        text = _local_name(text)
    return text if len(text) <= VALUE_CLIP else text[: VALUE_CLIP - 1] + "…"


def _size(value: Any) -> str:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return _short(value)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return str(value)


def payload_fields(payload: Any) -> list[tuple[str, str]]:
    """The informative ``(field, value)`` pairs of a payload, most telling first."""
    if not isinstance(payload, dict):
        return []
    fields = {
        k: v for k, v in payload.items() if k not in BOILERPLATE and v not in (None, "", [], {})
    }
    if "prefix" in fields and "key" in fields:
        fields["path"] = f"{str(fields.pop('prefix')).rstrip('/')}/{fields.pop('key')}"
    ordered = [k for k in PRIORITY if k in fields]
    ordered += [k for k in fields if k not in ordered and k not in LAST and k not in QUIET]
    ordered += [k for k in LAST if k in fields]
    out = []
    for key in ordered:
        value = _size(fields[key]) if key == "size_bytes" else _short(fields[key])
        out.append(("size" if key == "size_bytes" else key, value))
    return out


def payload_summary(payload: Any) -> str:
    return " · ".join(f"{k}={v}" for k, v in payload_fields(payload)[:SUMMARY_FIELDS])


def _payload(stored: Any) -> Any:
    try:
        return json.loads(stored.payload)
    except (ValueError, UnicodeDecodeError):
        return stored.payload.decode("utf-8", "replace")


def _clean(payload: Any) -> Any:
    """The payload without the plumbing every event repeats (the raw view keeps it)."""
    if not isinstance(payload, dict):
        return payload
    noise = {"_property_uris", "_class_uri"}
    return {k: v for k, v in payload.items() if k not in noise and v not in (None, "", [], {})}


def _cursor(cursor: str | None) -> int | None:
    if cursor is None:
        return None
    if not cursor.isdigit():
        raise InvalidResource(SERVICE, f"bad cursor {cursor!r}")
    return int(cursor)


class EventResources:
    service = SERVICE
    capabilities = ResourceCapabilities(browse=True, search=True)

    def __init__(self, events: Any) -> None:
        self._events = events

    # --- sync helpers, run in a worker thread ---------------------------------------

    def _types(self) -> dict[str, Any]:
        return {t.event_type: t for t in self._events.event_types()}

    def _type_entry(self, summary: Any) -> ResourceEntry:
        local = _local_name(summary.event_type)
        return ResourceEntry(
            _type_id(summary.event_type),
            humanize(local),
            "container",
            modified=summary.last_timestamp or None,
            attributes={
                "type": summary.event_type,
                "local_name": local,
                "domain": domain(summary.event_type),
                "count": str(summary.count),
                "last_seq": str(summary.last_seq),
                "summary": summary.event_type,
            },
        )

    @staticmethod
    def _event_entry(stored: Any) -> ResourceEntry:
        payload = _payload(stored)
        attributes = {
            "event_id": stored.id,
            "seq": str(stored.seq),
            "type": stored.event_type,
            "domain": domain(stored.event_type),
        }
        if isinstance(payload, dict):
            actor = payload.get("actor_user_id") or payload.get("creator")
            if actor:
                attributes["actor"] = str(actor)
            if payload.get("triggered_via"):
                attributes["via"] = str(payload["triggered_via"])
        summary = payload_summary(payload)
        if summary:
            attributes["summary"] = summary
        return ResourceEntry(
            f"{_type_id(stored.event_type)}/{stored.seq}",
            f"#{stored.seq}",
            "item",
            EVENT_ACTIONS,
            size=len(stored.payload),
            modified=stored.timestamp or None,
            attributes=attributes,
        )

    def _split(self, resource_id: str) -> tuple[str, int | None]:
        if not resource_id:
            raise InvalidResource(SERVICE, "an id is required")
        head, sep, tail = resource_id.partition("/")
        if not sep:
            return unquote(head), None
        if not tail.isdigit():
            raise ResourceNotFound(SERVICE, resource_id)
        return unquote(head), int(tail)

    def _stored(self, resource_id: str) -> Any:
        event_type, seq = self._split(resource_id)
        if seq is None:
            raise InvalidResource(SERVICE, f"{resource_id!r} is an event type")
        try:
            stored = self._events.get_stored(seq)
        except EventNotFoundError:
            raise ResourceNotFound(SERVICE, resource_id) from None
        if stored.event_type != event_type:
            raise ResourceNotFound(SERVICE, resource_id)
        return stored

    def _list(
        self, parent: str, cursor: str | None, limit: int, query: str | None = None
    ) -> ResourcePage:
        needle = (query or "").strip().lower()
        if not parent:
            entries = [self._type_entry(t) for t in self._types().values()]
            if needle:
                entries = [
                    e
                    for e in entries
                    if needle in e.name.lower() or needle in e.attributes["type"].lower()
                ]
            return paginate("", entries, cursor, limit)
        event_type, seq = self._split(parent)
        if seq is not None:
            raise InvalidResource(SERVICE, f"{parent!r} is an event")
        if event_type not in self._types():
            raise ResourceNotFound(SERVICE, parent)
        if limit < 1:
            raise InvalidResource(SERVICE, "limit must be positive")
        below = _cursor(cursor)
        rows = self._events.query_stored(
            event_type,
            until_seq=below - 1 if below is not None else None,
            limit=limit + 1,
            newest_first=True,
            search=needle or None,
        )
        page = rows[:limit]
        return ResourcePage(
            parent,
            tuple(self._event_entry(r) for r in page),
            next_cursor=str(page[-1].seq) if len(rows) > limit else None,
        )

    def _stat(self, resource_id: str) -> ResourceEntry:
        event_type, seq = self._split(resource_id)
        if seq is None:
            summary = self._types().get(event_type)
            if summary is None:
                raise ResourceNotFound(SERVICE, resource_id)
            return self._type_entry(summary)
        return self._event_entry(self._stored(resource_id))

    @staticmethod
    def _document(stored: Any) -> bytes:
        payload = _payload(stored)
        body = {
            "type": stored.event_type,
            "seq": stored.seq,
            "id": stored.id,
            "timestamp": stored.timestamp,
            "payload": payload,
        }
        return json.dumps(body, indent=2, ensure_ascii=False).encode()

    def _read(self, resource_id: str) -> ResourceDetail:
        stored = self._stored(resource_id)
        view = {"type": "json", "value": _clean(_payload(stored))}
        return ResourceDetail(
            self._event_entry(stored), text_preview(self._document(stored)), view=view
        )

    def _download(self, resource_id: str, max_bytes: int) -> bytes:
        data = self._document(self._stored(resource_id))
        if len(data) > max_bytes:
            raise ResourceTooLarge(SERVICE, resource_id, len(data), max_bytes)
        return data

    # --- ServiceResources --------------------------------------------------------------

    async def list(
        self, parent: str = "", *, cursor: str | None = None, limit: int = 100, **options: Any
    ) -> ResourcePage:
        return await asyncio.to_thread(self._list, parent, cursor, limit, options.get("query"))

    async def stat(self, resource_id: str) -> ResourceEntry:
        return await asyncio.to_thread(self._stat, resource_id)

    async def read(self, resource_id: str, *, reveal: bool = False) -> ResourceDetail:
        return await asyncio.to_thread(self._read, resource_id)

    async def download(self, resource_id: str, *, max_bytes: int) -> bytes:
        return await asyncio.to_thread(self._download, resource_id, max_bytes)

    async def write(self, resource_id: str, content: bytes) -> ResourceEntry:
        raise UnsupportedOperation(SERVICE, "write: the event log is append-only")

    async def delete(self, resource_id: str) -> None:
        raise UnsupportedOperation(SERVICE, "delete: the event log is append-only")
