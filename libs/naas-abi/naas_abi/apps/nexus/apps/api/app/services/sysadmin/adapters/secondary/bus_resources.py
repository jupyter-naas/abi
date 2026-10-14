"""JetStream as a tree: streams are containers, stored messages are items.

Ids are ``<stream>`` and ``<stream>/<sequence>``. A stream lists its messages
newest first, scanning sequences downward (deleted ones are skipped); the cursor
is the next sequence to scan. A message's payload is its value (bounded preview,
download); its subject, time and headers are attributes, with credential-like
header values redacted. Deleting removes one message.

``KV_*`` streams back key-value buckets (discovery's registry, the keyvalue
service): their messages are listed and readable but never deleted here, since
removing a revision behind the bucket's back corrupts its history. Manage those
entries through the owning service.

For a message browser: a stream carries its subjects as its summary and its last
activity (the time of its last message: one extra request per stream listed); a
message carries a one-line ``summary`` of its payload (JSON keys, the first
characters of text, or "binary") and ``payload`` (json, text or binary). Reading
a message adds a ``message`` view (subject, sequence, time, redacted headers).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import (
    JetStreamStream,
    SourceUnavailable,
)
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

SERVICE = "bus"
STREAM_PAGE = 256  # JetStream's stream list page size
MAX_STREAM_PAGES = 64
# A page scans at most this many sequences per entry asked for, so a stream
# with long runs of deleted messages still answers promptly.
SCAN_FACTOR = 8
REDACT = ("auth", "token", "secret", "password", "cookie", "credential")
REDACTED = "[REDACTED]"
SUMMARY_CHARS = 96


def payload_kind(data: bytes) -> str:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return "binary"
    if "\x00" in text:
        return "binary"
    try:
        json.loads(text)
    except ValueError:
        return "text"
    return "json"


def payload_summary(data: bytes) -> str:
    """One line: an object's keys, an array's length, text's start, or binary."""
    if not data:
        return "empty"
    kind = payload_kind(data)
    if kind == "binary":
        return f"binary · {len(data)} bytes"
    text = data.decode("utf-8")
    if kind == "json":
        value = json.loads(text)
        if isinstance(value, dict):
            keys = list(value)
            shown = ", ".join(keys[:6]) + (f", +{len(keys) - 6}" if len(keys) > 6 else "")
            return "{" + shown + "}"
        if isinstance(value, list):
            return f"[{len(value)} items]"
    line = " ".join(text.split())
    return line if len(line) <= SUMMARY_CHARS else line[: SUMMARY_CHARS - 1] + "…"


def stream_kind(name: str) -> str:
    return JetStreamStream(name, (), 0, 0, 0, 0, 0).kind


def _deletable(stream: str) -> bool:
    return stream_kind(stream) != "kv"


def _split(resource_id: str) -> tuple[str, int]:
    stream, _, seq = resource_id.partition("/")
    if not stream or not seq.isdigit() or int(seq) < 1:
        raise ResourceNotFound(SERVICE, resource_id)
    return stream, int(seq)


def redacted_headers(msg: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in (getattr(msg, "headers", None) or {}).items():
        sensitive = any(word in key.lower() for word in REDACT)
        out[key] = REDACTED if sensitive else str(value)
    return out


def _headers(msg: Any) -> dict[str, str]:
    return {f"header:{k}": v for k, v in redacted_headers(msg).items()}


def _time(msg: Any) -> str | None:
    value = getattr(msg, "time", None)
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


class BusResources:
    service = SERVICE
    capabilities = ResourceCapabilities(browse=True)

    def __init__(self, connect: Callable[[], Awaitable[Any]], *, timeout: float = 5.0) -> None:
        self._connect = connect
        self._timeout = timeout

    async def _jsm(self) -> Any:
        try:
            nc = await asyncio.wait_for(self._connect(), self._timeout)
        except Exception as exc:  # noqa: BLE001 - no broker, auth, timeout
            raise SourceUnavailable(
                "bus", f"NATS unreachable: {exc or type(exc).__name__}"
            ) from exc
        return nc.jsm(timeout=self._timeout)

    async def _call(self, call: Awaitable[Any]) -> Any:
        from nats.errors import NoRespondersError
        from nats.errors import TimeoutError as NatsTimeoutError
        from nats.js.errors import ServiceUnavailableError

        try:
            return await call
        except (NoRespondersError, ServiceUnavailableError) as exc:
            raise SourceUnavailable("bus", "JetStream is not enabled on this server") from exc
        except (NatsTimeoutError, TimeoutError, OSError) as exc:
            raise SourceUnavailable(
                "bus", f"JetStream did not answer: {type(exc).__name__}"
            ) from exc

    async def _stream(self, name: str) -> Any:
        from nats.js.errors import NotFoundError

        jsm = await self._jsm()
        try:
            return await self._call(jsm.stream_info(name))
        except NotFoundError:
            raise ResourceNotFound(SERVICE, name) from None

    async def _message(self, resource_id: str) -> Any:
        from nats.js.errors import NotFoundError

        stream, seq = _split(resource_id)
        await self._stream(stream)
        jsm = await self._jsm()
        try:
            return await self._call(jsm.get_msg(stream, seq))
        except NotFoundError:
            raise ResourceNotFound(SERVICE, resource_id) from None

    @staticmethod
    def _stream_entry(info: Any, last: Any = None) -> ResourceEntry:
        name, state = info.config.name, info.state
        subjects = ", ".join(info.config.subjects or ())
        attributes = {
            "kind": stream_kind(name),
            "subjects": subjects,
            "messages": str(state.messages),
            "consumers": str(state.consumer_count),
            "first_seq": str(state.first_seq),
            "last_seq": str(state.last_seq),
        }
        if subjects:
            attributes["summary"] = subjects
        if not _deletable(name):
            attributes["read_only"] = "key-value bucket"
        return ResourceEntry(
            name,
            name,
            "container",
            size=state.bytes,
            modified=_time(last) if last is not None else None,
            attributes=attributes,
        )

    @staticmethod
    def _message_entry(stream: str, msg: Any) -> ResourceEntry:
        actions: tuple[Action, ...] = ("read", "download")
        if _deletable(stream):
            actions += ("delete",)
        data = msg.data or b""
        return ResourceEntry(
            f"{stream}/{msg.seq}",
            msg.subject or str(msg.seq),
            "item",
            actions,
            size=len(data),
            modified=_time(msg),
            attributes={
                "seq": str(msg.seq),
                "subject": msg.subject or "",
                "payload": payload_kind(data) if data else "empty",
                "summary": payload_summary(data),
                **_headers(msg),
            },
        )

    async def _last_message(self, info: Any) -> Any:
        """The stream's newest message, for its last activity; None when gone."""
        if not info.state.messages:
            return None
        jsm = await self._jsm()
        try:
            return await self._call(jsm.get_msg(info.config.name, info.state.last_seq))
        except Exception:  # noqa: BLE001 - activity is a nicety; listing goes on
            return None

    async def _streams(self) -> list[Any]:
        jsm = await self._jsm()
        found: list[Any] = []
        for page in range(MAX_STREAM_PAGES):
            batch = await self._call(jsm.streams_info(offset=page * STREAM_PAGE))
            found.extend(batch)
            if len(batch) < STREAM_PAGE:
                break
        return sorted(found, key=lambda info: info.config.name)

    async def _messages(self, stream: str, cursor: str | None, limit: int) -> ResourcePage:
        from nats.js.errors import NotFoundError

        if limit < 1:
            raise InvalidResource(SERVICE, "limit must be positive")
        info = await self._stream(stream)
        first, last = info.state.first_seq, info.state.last_seq
        if cursor is not None and not cursor.isdigit():
            raise InvalidResource(SERVICE, f"bad cursor {cursor!r}")
        seq = min(int(cursor), last) if cursor is not None else last
        jsm = await self._jsm()
        entries: list[ResourceEntry] = []
        budget = limit * SCAN_FACTOR
        while seq >= max(first, 1) and len(entries) < limit and budget > 0:
            budget -= 1
            try:
                msg = await self._call(jsm.get_msg(stream, seq))
            except NotFoundError:
                seq -= 1
                continue
            entries.append(self._message_entry(stream, msg))
            seq -= 1
        more = seq >= max(first, 1)
        return ResourcePage(stream, tuple(entries), str(seq) if more else None)

    # --- ServiceResources --------------------------------------------------------------

    async def list(
        self, parent: str = "", *, cursor: str | None = None, limit: int = 100, **options: Any
    ) -> ResourcePage:
        if parent == "":
            infos = {info.config.name: info for info in await self._streams()}
            page = paginate("", [self._stream_entry(i) for i in infos.values()], cursor, limit)
            lasts = await asyncio.gather(*(self._last_message(infos[e.id]) for e in page.entries))
            entries = tuple(
                self._stream_entry(infos[e.id], last)
                for e, last in zip(page.entries, lasts, strict=True)
            )
            return ResourcePage("", entries, page.next_cursor)
        if "/" in parent:
            await self._message(parent)
            raise InvalidResource(SERVICE, f"{parent!r} is a message")
        return await self._messages(parent, cursor, limit)

    async def stat(self, resource_id: str) -> ResourceEntry:
        if resource_id == "":
            return ResourceEntry("", "", "container")
        if "/" not in resource_id:
            return self._stream_entry(await self._stream(resource_id))
        msg = await self._message(resource_id)
        return self._message_entry(_split(resource_id)[0], msg)

    async def read(self, resource_id: str, *, reveal: bool = False) -> ResourceDetail:
        if "/" not in resource_id:
            await self.stat(resource_id)
            raise InvalidResource(SERVICE, f"{resource_id!r} is a stream")
        msg = await self._message(resource_id)
        entry = self._message_entry(_split(resource_id)[0], msg)
        view = {
            "type": "message",
            "subject": msg.subject or "",
            "headers": redacted_headers(msg),
            "sequence": msg.seq,
            "published_at": _time(msg),
        }
        return ResourceDetail(entry, text_preview(msg.data or b""), view=view)

    async def download(self, resource_id: str, *, max_bytes: int) -> bytes:
        if "/" not in resource_id:
            await self.stat(resource_id)
            raise InvalidResource(SERVICE, f"{resource_id!r} is a stream")
        data = (await self._message(resource_id)).data or b""
        if len(data) > max_bytes:
            raise ResourceTooLarge(SERVICE, resource_id, len(data), max_bytes)
        return data

    async def write(self, resource_id: str, content: bytes) -> ResourceEntry:
        raise UnsupportedOperation(SERVICE, "write")

    async def delete(self, resource_id: str) -> None:
        from nats.js.errors import NotFoundError

        if "/" not in resource_id:
            await self.stat(resource_id)
            raise UnsupportedOperation(SERVICE, "delete a stream")
        stream, seq = _split(resource_id)
        await self._message(resource_id)
        if not _deletable(stream):
            raise UnsupportedOperation(SERVICE, "delete a key-value revision")
        jsm = await self._jsm()
        try:
            await self._call(jsm.delete_msg(stream, seq))
        except NotFoundError:
            raise ResourceNotFound(SERVICE, resource_id) from None
