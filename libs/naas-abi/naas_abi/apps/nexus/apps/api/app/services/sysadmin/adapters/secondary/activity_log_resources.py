"""The activity log, read-only: actors are containers, their events are items.

Wraps the engine's ``ActivityLogService`` (sync; calls run in a worker thread).
It is an audit trail, so nothing is written or deleted from here. Pages use
the store-assigned ``seq`` (``ActivityLogQuery.newest_first`` / ``before_seq``).

Ids: an actor is its id, percent-encoded (``/`` and all); an event is
``<actor id>/<seq>``. Events list newest first; the cursor is the last seq shown.

For a request log: an actor carries its kind (``user``, ``service``,
``anonymous``), its last activity (one newest-event query per actor on the page)
and, for ``user:<id>`` actors, a display name and email from ``actor_names`` (one
query for the page). An HTTP request is named by its path and carries method,
status, duration and client as attributes.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
from collections.abc import Awaitable, Callable, Mapping
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
from naas_abi_core.services.activity_log.ActivityLogPort import ActivityLogQuery

SERVICE = "activity_log"
EVENT_ACTIONS: tuple[Action, ...] = ("read", "download")
USER_PREFIX = "user:"

# ``{user id: (name, email)}`` for the ``user:<id>`` actors on a page.
ActorNames = Callable[[list[str]], Awaitable[Mapping[str, tuple[str, str]]]]


def _actor_id(actor: str) -> str:
    return quote(actor, safe="")


def actor_kind(actor: str) -> str:
    if actor == "anonymous":
        return "anonymous"
    head, sep, _ = actor.partition(":")
    return head if sep and head else "other"


def _request_summary(attributes: Mapping[str, Any]) -> str:
    parts = []
    query = attributes.get("query_params")
    if isinstance(query, dict) and query:
        parts.append("?" + "&".join(f"{k}={v}" for k, v in list(query.items())[:3]))
    if attributes.get("ip"):
        parts.append(str(attributes["ip"]))
    if attributes.get("error"):
        parts.append(f"error {attributes['error']}")
    agent = str(attributes.get("user_agent") or "")
    if agent:
        parts.append(agent.split(" ", 1)[0][:40])
    return " · ".join(parts)


def sql_actor_names(engine: Callable[[], Any]) -> ActorNames:
    """Names and emails of Nexus users, from its ``users`` table."""

    async def resolve(ids: list[str]) -> Mapping[str, tuple[str, str]]:
        if not ids:
            return {}
        from sqlalchemy import bindparam, text

        query = text("SELECT id, name, email FROM users WHERE id IN :ids").bindparams(
            bindparam("ids", expanding=True)
        )
        async with engine().connect() as conn:
            rows = (await conn.execute(query, {"ids": ids})).all()
        return {row[0]: (row[1] or "", row[2] or "") for row in rows}

    return resolve


class ActivityLogResources:
    service = SERVICE
    capabilities = ResourceCapabilities(browse=True)

    def __init__(self, activity_log: Any, *, actor_names: ActorNames | None = None) -> None:
        self._log = activity_log
        self._actor_names = actor_names

    # --- sync helpers, run in a worker thread ---------------------------------------

    def _actors(self) -> list[str]:
        return sorted(self._log.list_actors())

    @staticmethod
    def _actor_entry(actor: str, last: Any = None) -> ResourceEntry:
        return ResourceEntry(
            _actor_id(actor),
            actor,
            "container",
            modified=last.timestamp.isoformat() if last is not None else None,
            attributes={"actor": actor, "kind": actor_kind(actor)},
        )

    def _last_event(self, actor: str) -> Any:
        found = self._log.query(actor, ActivityLogQuery(newest_first=True, limit=1))
        return found[0] if found else None

    @staticmethod
    def _event_entry(event: Any) -> ResourceEntry:
        attrs = event.attributes or {}
        attributes = {"event_type": event.event_type, "seq": str(event.seq)}
        if event.correlation_id:
            attributes["correlation_id"] = event.correlation_id
        for key, name in (
            ("method", "method"),
            ("path", "path"),
            ("status_code", "status"),
            ("duration_ms", "duration_ms"),
            ("ip", "ip"),
        ):
            if attrs.get(key) not in (None, ""):
                attributes[name] = str(attrs[key])
        summary = _request_summary(attrs)
        if summary:
            attributes["summary"] = summary
        return ResourceEntry(
            f"{_actor_id(event.actor_id)}/{event.seq}",
            str(attrs.get("path") or event.event_type),
            "item",
            EVENT_ACTIONS,
            modified=event.timestamp.isoformat(),
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

    def _event(self, resource_id: str) -> Any:
        actor, seq = self._split(resource_id)
        if seq is None:
            raise InvalidResource(SERVICE, f"{resource_id!r} is an actor")
        found = self._log.query(actor, ActivityLogQuery(after_seq=seq - 1, limit=1))
        if not found or found[0].seq != seq:
            raise ResourceNotFound(SERVICE, resource_id)
        return found[0]

    def _list(self, parent: str, cursor: str | None, limit: int) -> ResourcePage:
        if not parent:
            actors = paginate("", [self._actor_entry(a) for a in self._actors()], cursor, limit)
            # Last activity only for the actors on this page: one query each.
            entries = tuple(
                self._actor_entry(e.attributes["actor"], self._last_event(e.attributes["actor"]))
                for e in actors.entries
            )
            return dataclasses.replace(actors, entries=entries)
        actor, seq = self._split(parent)
        if seq is not None:
            raise InvalidResource(SERVICE, f"{parent!r} is an event")
        if actor not in self._actors():
            raise ResourceNotFound(SERVICE, parent)
        if limit < 1:
            raise InvalidResource(SERVICE, "limit must be positive")
        if cursor is not None and not cursor.isdigit():
            raise InvalidResource(SERVICE, f"bad cursor {cursor!r}")
        rows = self._log.query(
            actor,
            ActivityLogQuery(
                newest_first=True,
                before_seq=int(cursor) if cursor is not None else None,
                limit=limit + 1,
            ),
        )
        page = [e for e in rows[:limit] if e.seq is not None]
        return ResourcePage(
            parent,
            tuple(self._event_entry(e) for e in page),
            next_cursor=str(page[-1].seq) if len(rows) > limit and page else None,
        )

    def _stat(self, resource_id: str) -> ResourceEntry:
        actor, seq = self._split(resource_id)
        if seq is None:
            if actor not in self._actors():
                raise ResourceNotFound(SERVICE, resource_id)
            return self._actor_entry(actor)
        return self._event_entry(self._event(resource_id))

    @staticmethod
    def _document(event: Any) -> bytes:
        body = {
            "actor_id": event.actor_id,
            "seq": event.seq,
            "event_type": event.event_type,
            "timestamp": event.timestamp.isoformat(),
            "correlation_id": event.correlation_id,
            "attributes": event.attributes,
        }
        return json.dumps(body, indent=2, ensure_ascii=False, default=str).encode()

    def _read(self, resource_id: str) -> ResourceDetail:
        event = self._event(resource_id)
        document = self._document(event)
        view = {"type": "json", "value": json.loads(document)}
        return ResourceDetail(self._event_entry(event), text_preview(document), view=view)

    def _download(self, resource_id: str, max_bytes: int) -> bytes:
        data = self._document(self._event(resource_id))
        if len(data) > max_bytes:
            raise ResourceTooLarge(SERVICE, resource_id, len(data), max_bytes)
        return data

    # --- ServiceResources --------------------------------------------------------------

    async def list(
        self, parent: str = "", *, cursor: str | None = None, limit: int = 100, **options: Any
    ) -> ResourcePage:
        page = await asyncio.to_thread(self._list, parent, cursor, limit)
        if parent or self._actor_names is None:
            return page
        return dataclasses.replace(page, entries=await self._named(page.entries))

    async def _named(self, entries: tuple[ResourceEntry, ...]) -> tuple[ResourceEntry, ...]:
        """Users shown by name, their id and email underneath. Best effort."""
        users = [
            e.attributes["actor"][len(USER_PREFIX) :]
            for e in entries
            if e.attributes["actor"].startswith(USER_PREFIX)
        ]
        try:
            names = await self._actor_names(users) if users and self._actor_names else {}
        except Exception:  # noqa: BLE001 - names are a nicety; the log still lists
            names = {}
        out = []
        for entry in entries:
            actor = entry.attributes["actor"]
            name, email = names.get(actor[len(USER_PREFIX) :], ("", ""))
            if not (name or email):
                out.append(entry)
                continue
            attributes = {**entry.attributes, "user_name": name, "email": email}
            attributes["summary"] = " · ".join(filter(None, [email, actor]))
            out.append(dataclasses.replace(entry, name=name or email, attributes=attributes))
        return tuple(out)

    async def stat(self, resource_id: str) -> ResourceEntry:
        return await asyncio.to_thread(self._stat, resource_id)

    async def read(self, resource_id: str, *, reveal: bool = False) -> ResourceDetail:
        return await asyncio.to_thread(self._read, resource_id)

    async def download(self, resource_id: str, *, max_bytes: int) -> bytes:
        return await asyncio.to_thread(self._download, resource_id, max_bytes)

    async def write(self, resource_id: str, content: bytes) -> ResourceEntry:
        raise UnsupportedOperation(SERVICE, "write: the activity log is an audit trail")

    async def delete(self, resource_id: str) -> None:
        raise UnsupportedOperation(SERVICE, "delete: the activity log is an audit trail")
