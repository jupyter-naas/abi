"""LangGraph checkpoints kept in the document service, made readable.

The document checkpointers (``naas_abi_sdk.langgraph`` and core's engine saver,
schema in ``naas_abi_sdk.langgraph_documents``) store, per namespace and agent:

- schema 2: ``langgraph_checkpoints_v2`` (scope, ids, parent, ``checkpoint`` and
  ``metadata`` without the values, and ``channels``: each value inline or a
  reference), with the values in ``langgraph_blobs_v2`` / ``langgraph_items_v2``
  / ``langgraph_parts_v2`` and pending writes in ``langgraph_writes_v2``;
- schema 1: ``langgraph_checkpoints_v1`` (the whole checkpoint inline) and
  ``langgraph_writes_v1``.

Values are LangGraph ``dumps_typed`` msgpack with its extension types: (module,
class, arguments). This decodes them without importing or constructing
anything. Objects become ``{"$type": "module.Class", ...fields}``, secrets
(``SecretStr``) are masked, pickle is never loaded, and anything unreadable or
not fetched is described instead of raising. The caller fetches the referenced
documents (``references`` / ``tail_references``) and passes them as ``fetched``.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from datetime import date, datetime, time
from typing import Any

from naas_abi_sdk.langgraph_documents import (
    CHECKPOINTS,
    DOCUMENT_OVERHEAD,
    LEGACY_CHECKPOINTS,
    LEGACY_WRITES,
    PART_SIZE,
    WRITES,
    raw_channel_values,
    raw_value,
)

try:  # LangGraph's own msgpack codec; absent, values are only described.
    import ormsgpack
except ImportError:  # pragma: no cover - the API ships with LangGraph
    ormsgpack = None  # type: ignore[assignment]

CHECKPOINT_COLLECTIONS = (CHECKPOINTS, LEGACY_CHECKPOINTS)
WRITE_COLLECTIONS = (WRITES, LEGACY_WRITES)
MASK = "••••••"
# One message shows this much text; the rest is cut (and flagged).
MESSAGE_CHARS = 20_000
SNIPPET = 80

# LangGraph's msgpack extension codes (langgraph.checkpoint.serde.jsonplus).
_SINGLE_ARG, _POS_ARGS, _KW_ARGS, _METHOD_SINGLE_ARG = 0, 1, 2, 3
_PYDANTIC_V1, _PYDANTIC_V2, _NUMPY = 4, 5, 6
# Values of these modules read better as their plain argument (UUIDs, dates, sets).
_PLAIN_MODULES = {"builtins", "uuid", "decimal", "datetime", "pathlib", "ipaddress", "zoneinfo"}
_ROLES = {"human": "human", "ai": "ai", "tool": "tool", "system": "system", "function": "tool"}


def document_key(agent_id: str, *parts: Any) -> str:
    """A saver document's id, as ``DocumentCheckpointSaver._key`` derives it."""
    return hashlib.sha256(json.dumps([agent_id, *parts], ensure_ascii=True).encode()).hexdigest()


def _plain(value: Any) -> Any:
    """JSON-safe: bytes and odd numbers described, dates as ISO, keys as text."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, (bytes, bytearray)):
        return f"<{len(value)} bytes>"
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_plain(v) for v in value]
    return str(value)


def _object(module: str, name: str, fields: Any) -> Any:
    kind = f"{module}.{name}"
    if "Secret" in name:
        return {"$type": kind, "value": MASK}
    if isinstance(fields, dict):
        return {"$type": kind, **fields}
    return {"$type": kind, "value": fields}


def _ext_hook(code: int, data: bytes) -> Any:
    try:
        parts = ormsgpack.unpackb(data, ext_hook=_ext_hook, option=ormsgpack.OPT_NON_STR_KEYS)
    except Exception:  # noqa: BLE001 - a damaged extension is described, not fatal
        return {"$type": f"<undecodable extension {code}>", "size": len(data)}
    if code == _NUMPY:
        dtype, shape = (
            (parts[0], parts[1])
            if isinstance(parts, (list, tuple)) and len(parts) > 1
            else (None, None)
        )
        return {"$type": "numpy.ndarray", "dtype": str(dtype), "shape": _plain(shape)}
    if not isinstance(parts, (list, tuple)) or len(parts) < 3:
        return {"$type": f"<extension {code}>", "size": len(data)}
    module, name, args = str(parts[0]), str(parts[1]), parts[2]
    if (
        code in (_SINGLE_ARG, _METHOD_SINGLE_ARG)
        and module.split(".")[0] in _PLAIN_MODULES
        and "Secret" not in name
    ):
        return args
    if code == _POS_ARGS:
        return _object(
            module, name, {"args": list(args) if isinstance(args, (list, tuple)) else args}
        )
    return _object(module, name, args)


def stored_value(value: Any, fetched: Mapping[str, Any] | None = None) -> Any:
    """A stored value (inline, or split into fetched parts) as plain JSON."""
    if isinstance(value, Mapping) and "parts" in value:
        try:
            value = raw_value(value, fetched or {})
        except (KeyError, ValueError):
            return {
                "$type": f"<{value.get('kind')}>",
                "size": value.get("size"),
                "note": "in parts, not loaded",
            }
    return decode_typed(value)


def _channel_values(data: Mapping[str, Any], fetched: Mapping[str, Any]) -> dict[str, Any]:
    """Schema 2 channel values, each decoded; what was not fetched is described."""
    shown: dict[str, Any] = {}
    for channel, entry in (data.get("channels") or {}).items():
        try:
            raw = raw_channel_values({"channels": {channel: entry}}, fetched)[channel]
        except (KeyError, ValueError):
            shown[channel] = {"$type": "<not loaded>"}
            continue
        shown[channel] = (
            [decode_typed(item) for item in raw] if isinstance(raw, list) else decode_typed(raw)
        )
    return shown


def tail_references(data: Mapping[str, Any], fetched: Mapping[str, Any]) -> list[tuple[str, int]]:
    """What a listing reads next to count a schema 2 conversation and show its last
    message: the messages blob, its last chunk, then the last element (never parts)."""
    entry = (data.get("channels") or {}).get("messages") or {}
    ref = entry.get("blob")
    if not ref:
        return []
    blob = fetched.get(ref)
    if blob is None:
        return [(ref, PART_SIZE + DOCUMENT_OVERHEAD)]
    chunks = blob.get("chunks")
    if not chunks:
        return []
    chunk = fetched.get(chunks[-1])
    if chunk is None:
        return [(chunks[-1], DOCUMENT_OVERHEAD * 2)]
    if not chunk["elements"]:
        return []
    last, size = chunk["elements"][-1]
    if last in fetched or size > PART_SIZE:
        return []
    return [(last, size + DOCUMENT_OVERHEAD)]


def _tail(data: Mapping[str, Any], fetched: Mapping[str, Any]) -> tuple[int, Any] | None:
    """(message count, last message) of a schema 2 messages blob, if fetched."""
    entry = (data.get("channels") or {}).get("messages") or {}
    blob = fetched.get(entry.get("blob", ""))
    if not blob or "chunks" not in blob:
        return None
    last = None
    chunk = fetched.get(blob["chunks"][-1]) if blob["chunks"] else None
    if chunk and chunk["elements"]:
        element = fetched.get(chunk["elements"][-1][0])
        if element is not None:
            last = stored_value(element["value"], fetched)
    return blob["length"], last


def decode_typed(value: Any) -> Any:
    """A ``{"kind", "payload"}`` value as plain JSON, never loading pickle."""
    if not isinstance(value, dict) or "kind" not in value:
        return _plain(value)
    kind, payload = value.get("kind"), value.get("payload") or b""
    size = len(payload) if isinstance(payload, (bytes, bytearray, str)) else 0
    if kind == "null":
        return None
    if kind in ("bytes", "bytearray"):
        return f"<{size} bytes>"
    try:
        if kind == "json":
            return _plain(json.loads(payload))
        if kind == "msgpack" and ormsgpack is not None:
            return _plain(
                ormsgpack.unpackb(payload, ext_hook=_ext_hook, option=ormsgpack.OPT_NON_STR_KEYS)
            )
    except Exception:  # noqa: BLE001
        return {"$type": f"<undecodable {kind}>", "size": size}
    return {"$type": f"<{kind}>", "size": size, "note": "not decoded"}


# --- messages ---------------------------------------------------------------------------


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                kind = part.get("type", "part")
                parts.append(str(part.get("text", "")) if kind == "text" else f"[{kind}]")
        return "\n".join(parts)
    return json.dumps(content, ensure_ascii=False)


def _is_message(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and "content" in value
        and (
            "langchain_core.messages" in str(value.get("$type", "")) or value.get("type") in _ROLES
        )
    )


def message(value: dict[str, Any]) -> dict[str, Any]:
    """A LangChain message as role, text, tool calls and usage."""
    kind = str(value.get("type") or "")
    role = _ROLES.get(kind) or ("ai" if kind.lower().startswith("ai") else kind or "message")
    text = _text(value.get("content"))
    shown: dict[str, Any] = {"role": role, "content": text[:MESSAGE_CHARS]}
    if len(text) > MESSAGE_CHARS:
        shown["truncated"] = len(text)
    for key in ("name", "id", "tool_call_id", "status"):
        if value.get(key):
            shown[key] = value[key]
    calls = value.get("tool_calls") or []
    if calls:
        shown["tool_calls"] = [
            {"id": c.get("id"), "name": c.get("name"), "args": c.get("args")}
            for c in calls
            if isinstance(c, dict)
        ]
    usage = value.get("usage_metadata")
    if isinstance(usage, dict):
        shown["usage"] = {
            k: usage[k] for k in ("input_tokens", "output_tokens", "total_tokens") if k in usage
        }
    metadata = value.get("response_metadata") or {}
    model = (
        metadata.get("model_name") or metadata.get("model") if isinstance(metadata, dict) else None
    )
    if model:
        shown["model"] = model
    return shown


def _snippet(shown: dict[str, Any]) -> str:
    text = " ".join(str(shown.get("content", "")).split())
    if not text and shown.get("tool_calls"):
        text = "calls " + ", ".join(str(c.get("name")) for c in shown["tool_calls"])
    return text if len(text) <= SNIPPET else text[: SNIPPET - 1] + "…"


# --- documents --------------------------------------------------------------------------


def write(data: dict[str, Any], fetched: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """One pending write: its task, channel and decoded value."""
    return {
        "task_id": data.get("task_id"),
        "task_path": data.get("task_path"),
        "channel": data.get("channel"),
        "index": data.get("index"),
        "value": _messages_in(stored_value(data.get("value"), fetched)),
    }


def _messages_in(value: Any) -> Any:
    if _is_message(value):
        return message(value)
    if isinstance(value, list) and value and all(_is_message(v) for v in value):
        return [message(v) for v in value]
    return value


def checkpoint_view(
    data: dict[str, Any],
    writes: list[dict[str, Any]],
    parent_entry: str | None,
    fetched: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """The ``checkpoint`` view of a checkpoint document (shape in ``ResourceDetail``).

    Schema 2 values come from ``fetched`` (documents by ref); schema 1 is inline.
    """
    fetched = fetched or {}
    checkpoint = stored_value(data.get("checkpoint"), fetched)
    metadata = stored_value(data.get("metadata"), fetched)
    checkpoint = checkpoint if isinstance(checkpoint, dict) else {}
    metadata = metadata if isinstance(metadata, dict) else {}
    if "channels" in data:
        channels: Any = _channel_values(data, fetched)
    else:
        channels = checkpoint.get("channel_values")
    channels = channels if isinstance(channels, dict) else {}
    raw = channels.get("messages")
    messages = [message(m) for m in raw if _is_message(m)] if isinstance(raw, list) else []
    return {
        "type": "checkpoint",
        "agent_id": data.get("agent_id"),
        "thread_id": data.get("thread_id"),
        "checkpoint_ns": data.get("checkpoint_ns"),
        "checkpoint_id": data.get("checkpoint_id"),
        "parent_id": data.get("parent_id"),
        "parent_entry": parent_entry,
        "created_at": checkpoint.get("ts"),
        "step": metadata.get("step"),
        "source": metadata.get("source"),
        "messages": messages,
        "channels": {k: _messages_in(v) for k, v in channels.items() if k != "messages"},
        "metadata": metadata,
        "writes": [write(w, fetched) for w in writes],
    }


def checkpoint_attributes(
    data: dict[str, Any], fetched: Mapping[str, Any] | None = None
) -> dict[str, str]:
    """Listing attributes: thread, agent, step, source, message count, last message.

    For schema 2, ``fetched`` holds what ``tail_references`` asked for.
    """
    view = checkpoint_view(data, [], None, fetched)
    messages = view["messages"]
    tail = _tail(data, fetched or {})
    if tail is not None:
        count, last_value = tail
        messages = [message(last_value)] if _is_message(last_value) else []
    else:
        count = len(messages)
    attributes = {
        "thread": str(view["thread_id"] or ""),
        "agent": str(view["agent_id"] or ""),
        "messages": str(count),
    }
    if view["step"] is not None:
        attributes["step"] = str(view["step"])
    if view["source"]:
        attributes["source"] = str(view["source"])
    if view["created_at"]:
        attributes["checkpoint_at"] = str(view["created_at"])
    last = f"{messages[-1]['role']}: {_snippet(messages[-1])}" if messages else None
    if last:
        attributes["last"] = last
    count_text = f"{count} message{'' if count == 1 else 's'}"
    parts = [
        f"step {view['step']}" if view["step"] is not None else None,
        view["source"],
        count_text,
        last,
    ]
    attributes["summary"] = " · ".join(str(p) for p in parts if p)
    return attributes


def write_attributes(data: dict[str, Any]) -> dict[str, str]:
    """Listing attributes of a pending write (a value split in parts is described)."""
    shown = write(data)
    value = shown["value"]
    if isinstance(value, dict) and "role" in value:
        brief = f"{value['role']}: {_snippet(value)}"
    elif isinstance(value, list) and value and isinstance(value[0], dict) and "role" in value[0]:
        brief = f"{len(value)} message{'' if len(value) == 1 else 's'}, {value[-1]['role']}: {_snippet(value[-1])}"
    else:
        text = json.dumps(value, ensure_ascii=False)
        brief = text if len(text) <= SNIPPET else text[: SNIPPET - 1] + "…"
    return {
        "thread": str(data.get("thread_id") or ""),
        "agent": str(data.get("agent_id") or ""),
        "channel": str(shown["channel"] or ""),
        "task": str(shown["task_path"] or ""),
        "index": str(shown["index"]),
        "summary": f"{shown['channel']} ← {brief}",
    }
