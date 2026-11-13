"""How LangGraph checkpoints are stored as documents: one schema, two savers.

``naas_abi_sdk.langgraph.DocumentCheckpointSaver`` (async, document RPCs) and
naas_abi_core's ``DocumentCheckpointSaver`` (synchronous, the engine's document
service) both plan their writes and decode their reads here, so the stored
documents are identical and a thread moves between them. The savers only do I/O.

Schema 2 stores increments. A checkpoint document keeps its scope, ids, parent,
metadata and the checkpoint without its values; each channel value is inline
when small, else a reference to a blob. Blobs and list elements are
content-addressed within the thread, so a step writes only what is new:

- ``langgraph_checkpoints_v2``: one per checkpoint, create-only.
- ``langgraph_blobs_v2``: a channel value, or the chunk list of a list value.
- ``langgraph_items_v2``: one list element (``e-``), or a chunk of element
  references with their sizes (``c-``). Appending to ``messages`` writes the new
  messages, the last chunk and a small blob.
- ``langgraph_parts_v2``: any serialized value above ``PART_SIZE``, split.
- ``langgraph_writes_v2``: pending writes; ordinary ones first-write-wins,
  special error/interrupt ones (negative index) are updates.

Documents a checkpoint references are written before it, and only
``delete_thread`` or retention (``kept_checkpoints``: the newest checkpoints of
a thread and the subgraph steps they ran, with every document they reference)
removes them, so a stored checkpoint is always complete. No document exceeds
``PART_SIZE`` plus small fields, and reads fetch by reference in batches of at
most ``READ_BUDGET`` bytes. Schema 1 (``*_v1``, full snapshots) is still read.
The sysadmin viewer reads values with ``references``, ``resolution`` and
``raw_channel_values``, without deserializing anything.

Secrets (``SecretStr``, ``SecretBytes``, anything with ``get_secret_value``)
are never written: values are serialized through ``RedactingSerializer``, and
read back holding ``REDACTED_SECRET``. Checkpoints leave the process and the
Data tab shows raw documents; a graph that needs a credential across steps
keeps its name and resolves it from the secret service when it uses it.

Needs langgraph-checkpoint (the [langgraph] extra). Keep it importable on the
SDK's oldest Python and never import it from the package ``__init__``.
"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib
import json
import sys
import threading
from collections import OrderedDict
from collections.abc import Generator, Iterable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Literal, NamedTuple

import ormsgpack
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    RunnableConfig,
    get_checkpoint_metadata,
)
from langgraph.checkpoint.serde.base import SerializerProtocol
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

SCHEMA_VERSION = 2
CHECKPOINTS = "langgraph_checkpoints_v2"
WRITES = "langgraph_writes_v2"
BLOBS = "langgraph_blobs_v2"
ITEMS = "langgraph_items_v2"
PARTS = "langgraph_parts_v2"
LEGACY_CHECKPOINTS = "langgraph_checkpoints_v1"
LEGACY_WRITES = "langgraph_writes_v1"

# Largest serialized value one document holds; larger ones are split into parts.
PART_SIZE = 256 * 1024
# Channel values up to this size stay in the checkpoint document.
INLINE_LIMIT = 1024
# List elements per chunk: appending rewrites one chunk of at most this many refs.
CHUNK_SIZE = 32
# Bytes one read may fetch, whatever the content: a quarter of the 8 MiB broker
# limit. A single document above it (one part plus fields) is read alone.
READ_BUDGET = 2 * 1024 * 1024
MAX_IN_VALUES = 500
# Fields and framing a document adds to the value it holds.
DOCUMENT_OVERHEAD = 4 * 1024
# Page sizes keep a page of whole documents within READ_BUDGET: a checkpoint
# holds at most two stored values plus small inline channel values.
CHECKPOINT_PAGE = READ_BUDGET // (2 * PART_SIZE + 16 * DOCUMENT_OVERHEAD)
WRITE_PAGE = READ_BUDGET // (PART_SIZE + DOCUMENT_OVERHEAD)
LEGACY_PAGE = 1  # schema 1 documents are full snapshots of any size

SCOPE_FIELDS = ("agent_id", "thread_id", "checkpoint_ns", "checkpoint_id")
REF_FIELDS = ("agent_id", "thread_id", "ref")
# Indexed string fields of each collection; every query filters on them.
COLLECTIONS: dict[str, tuple[str, ...]] = {
    CHECKPOINTS: SCOPE_FIELDS,
    WRITES: SCOPE_FIELDS,
    BLOBS: REF_FIELDS,
    ITEMS: REF_FIELDS,
    PARTS: REF_FIELDS,
}
# Checkpoint IDs are time-ordered: newest first, as LangGraph's own savers list.
NEWEST_FIRST: tuple[str, Literal["desc"]] = ("checkpoint_id", "desc")

_REF_COLLECTIONS = {"b": BLOBS, "c": ITEMS, "e": ITEMS, "p": PARTS}
_CHUNK_BYTES = CHUNK_SIZE * 100 + DOCUMENT_OVERHEAD  # entries: a ref and a size
_STORED_BYTES = PART_SIZE + DOCUMENT_OVERHEAD


def next_version(current: Any) -> Any:
    """The channel version after ``current``, keeping the thread's version type.

    LangGraph derives a step's version from the highest one in the checkpoint,
    so each thread keeps one type: new threads count in integers (LangGraph's
    default), threads written by its PostgreSQL or in-memory savers keep their
    ``"<counter>.<random>"`` strings. Mixing both in a thread breaks comparisons.
    Stored values are content-addressed, so versions need not be unique.
    """
    if current is None:
        return 1
    if isinstance(current, str):
        return f"{int(current.split('.')[0]) + 1:032}.{0.0:016}"
    return current + 1


# --- secrets --------------------------------------------------------------------------

REDACTED_SECRET = "[REDACTED: secrets are not stored in checkpoints]"
_REDACT_DEPTH = 64  # values nest deeper only by mistake (or a cycle)


def redact_secrets(value: Any) -> Any:
    """``value`` with every secret (anything with ``get_secret_value``, as
    pydantic's ``SecretStr``/``SecretBytes``) replaced by one of the same type
    holding ``REDACTED_SECRET``. Walks dicts, lists, tuples, sets, pydantic
    models (messages included) and dataclasses; returns ``value`` itself, not a
    copy, when it holds no secret."""
    return _redact(value, 0)


def _redacted(secret: Any) -> Any:
    marker: Any = REDACTED_SECRET
    if isinstance(secret.get_secret_value(), (bytes, bytearray)):
        marker = REDACTED_SECRET.encode()
    try:
        return type(secret)(marker)
    except Exception:  # noqa: BLE001 - an unusual secret type: never its value
        return marker


def _redact(value: Any, depth: int) -> Any:
    if depth > _REDACT_DEPTH or isinstance(
        value, (str, bytes, bytearray, int, float, type(None))
    ):
        return value
    if not isinstance(value, type) and callable(
        getattr(value, "get_secret_value", None)
    ):
        return _redacted(value)
    if isinstance(value, dict):
        items = {key: _redact(item, depth + 1) for key, item in value.items()}
        if all(items[key] is value[key] for key in value):
            return value
        return items if type(value) is dict else type(value)(items)
    if isinstance(value, (list, tuple, set, frozenset)):
        members = [_redact(item, depth + 1) for item in value]
        if all(new is old for new, old in zip(members, value)):
            return value
        if isinstance(value, tuple) and hasattr(value, "_fields"):  # namedtuple
            return type(value)(*members)
        return type(value)(members)
    if dataclasses.is_dataclass(value):
        changes = {}
        for field in dataclasses.fields(value):
            if field.init:
                current = getattr(value, field.name)
                new = _redact(current, depth + 1)
                if new is not current:
                    changes[field.name] = new
        return dataclasses.replace(value, **changes) if changes else value  # type: ignore[type-var]
    model_fields = getattr(type(value), "model_fields", None)
    if isinstance(model_fields, dict) and callable(getattr(value, "model_copy", None)):
        names = [*model_fields, *(getattr(value, "__pydantic_extra__", None) or {})]
        changes = {}
        for name in names:
            current = getattr(value, name, None)
            new = _redact(current, depth + 1)
            if new is not current:
                changes[name] = new
        return value.model_copy(update=changes) if changes else value
    return value


# --- decoding ---------------------------------------------------------------------------

# Values a checkpoint may rebuild from the standard library (and pydantic's
# redacted secrets), by exact symbol.
_STDLIB_VALUES = frozenset(
    {
        ("builtins", "set"),
        ("builtins", "frozenset"),
        ("collections", "deque"),
        ("datetime", "date"),
        ("datetime", "datetime"),
        ("datetime", "time"),
        ("datetime", "timedelta"),
        ("datetime", "timezone"),
        ("decimal", "Decimal"),
        ("ipaddress", "IPv4Address"),
        ("ipaddress", "IPv4Interface"),
        ("ipaddress", "IPv4Network"),
        ("ipaddress", "IPv6Address"),
        ("ipaddress", "IPv6Interface"),
        ("ipaddress", "IPv6Network"),
        ("pathlib", "Path"),
        ("pathlib", "PosixPath"),
        ("pathlib", "PurePath"),
        ("pathlib", "PurePosixPath"),
        ("pathlib", "PureWindowsPath"),
        ("pathlib", "WindowsPath"),
        ("pydantic.types", "SecretBytes"),
        ("pydantic.types", "SecretStr"),
        ("pydantic.v1.types", "SecretBytes"),
        ("pydantic.v1.types", "SecretStr"),
        ("uuid", "UUID"),
        ("zoneinfo", "ZoneInfo"),
    }
)
# The one method a stored value may name: rebuilding a date or time from text.
_STDLIB_METHODS = frozenset(
    {
        ("datetime", "date", "fromisoformat"),
        ("datetime", "datetime", "fromisoformat"),
        ("datetime", "time", "fromisoformat"),
    }
)
# Packages whose value classes (pydantic models, dataclasses, enums, named
# tuples) a checkpoint may rebuild, once the process has imported them.
_VALUE_PACKAGES = ("langchain_core", "langgraph", "naas_abi_core", "naas_abi_sdk", "naas_abi")

_EXT_CONSTRUCTOR_SINGLE_ARG = 0
_EXT_CONSTRUCTOR_POS_ARGS = 1
_EXT_CONSTRUCTOR_KW_ARGS = 2
_EXT_METHOD_SINGLE_ARG = 3
_EXT_PYDANTIC_V1 = 4
_EXT_PYDANTIC_V2 = 5
_EXT_NUMPY_ARRAY = 6


def _is_value_class(obj: Any) -> bool:
    if not isinstance(obj, type) or issubclass(obj, BaseException):
        return False
    if dataclasses.is_dataclass(obj) or issubclass(obj, Enum):
        return True
    if issubclass(obj, tuple) and hasattr(obj, "_fields"):
        return True
    return callable(getattr(obj, "model_validate", None)) or callable(
        getattr(obj, "parse_obj", None)
    )


def _value_class(module: Any, name: Any, packages: tuple[str, ...]) -> Any | None:
    """The class a stored value names, if a checkpoint may rebuild it.

    Standard library values are named exactly. Other classes must be value
    classes of an allowed package that this process has already imported:
    nothing stored ever imports a module or calls a function.
    """
    if not isinstance(module, str) or not isinstance(name, str):
        return None
    if (module, name) in _STDLIB_VALUES:
        return getattr(importlib.import_module(module), name)
    if not any(module == p or module.startswith(p + ".") for p in packages):
        return None
    loaded = sys.modules.get(module)
    obj = getattr(loaded, name, None) if loaded is not None else None
    return obj if _is_value_class(obj) else None


class CheckpointSerializer(JsonPlusSerializer):
    """LangGraph's serializer, decoding stored values as data.

    Writes exactly as ``JsonPlusSerializer``. Reads rebuild only value classes
    (``_value_class``): a stored value that names anything else comes back as
    its fields (a model or dataclass) or as ``None``, and is never imported or
    called. ``json`` values are plain JSON and pickles are refused.
    ``packages`` adds packages whose value classes may be rebuilt.
    """

    def __init__(self, *, packages: Iterable[str] = ()) -> None:
        self._packages = (*_VALUE_PACKAGES, *packages)
        super().__init__(__unpack_ext_hook__=self._ext_hook)

    def loads_typed(self, data: tuple[str, bytes]) -> Any:
        kind, payload = data
        if kind == "json":
            return json.loads(payload)
        if kind not in ("null", "bytes", "bytearray", "msgpack"):
            raise NotImplementedError(f"Unknown serialization type: {kind}")
        return super().loads_typed(data)

    def _unpack(self, data: bytes) -> Any:
        return ormsgpack.unpackb(
            data, ext_hook=self._ext_hook, option=ormsgpack.OPT_NON_STR_KEYS
        )

    def _ext_hook(self, code: int, data: bytes) -> Any:
        try:
            fields = self._unpack(data)
        except Exception:  # noqa: BLE001 - an unreadable value reads as nothing
            return None
        try:
            return self._rebuild(code, fields)
        except Exception:  # noqa: BLE001
            # As LangGraph does: a model it cannot rebuild reads as its fields.
            if code in (_EXT_PYDANTIC_V1, _EXT_PYDANTIC_V2, _EXT_CONSTRUCTOR_KW_ARGS):
                return _fields_of(fields)
            return None

    def _rebuild(self, code: int, fields: Any) -> Any:
        if code == _EXT_NUMPY_ARRAY:
            numpy = sys.modules.get("numpy")
            dtype_str, shape, order, buf = fields
            dtype = numpy.dtype(dtype_str) if numpy is not None else None
            if dtype is None or dtype.hasobject:
                return None
            return numpy.frombuffer(buf, dtype=dtype).reshape(shape, order=order)
        if code == _EXT_METHOD_SINGLE_ARG:
            module, name, arg, method = fields
            if (module, name, method) not in _STDLIB_METHODS:
                return None
            cls = getattr(importlib.import_module(module), name)
            return getattr(cls, method)(arg)
        cls = _value_class(fields[0], fields[1], self._packages)
        if cls is None:
            if code in (_EXT_PYDANTIC_V1, _EXT_PYDANTIC_V2, _EXT_CONSTRUCTOR_KW_ARGS):
                return _fields_of(fields)
            return None
        if code == _EXT_CONSTRUCTOR_SINGLE_ARG:
            return cls(fields[2])
        if code == _EXT_CONSTRUCTOR_POS_ARGS:
            return cls(*fields[2])
        if code == _EXT_CONSTRUCTOR_KW_ARGS:
            return cls(**fields[2])
        if code == _EXT_PYDANTIC_V2:
            try:
                return cls(**fields[2])
            except Exception:  # noqa: BLE001
                return cls.model_construct(**fields[2])
        if code == _EXT_PYDANTIC_V1:
            try:
                return cls(**fields[2])
            except Exception:  # noqa: BLE001
                return cls.construct(**fields[2])
        return None


def _fields_of(fields: Any) -> Any:
    return fields[2] if isinstance(fields, (list, tuple)) and len(fields) > 2 else None


def checkpoint_serde() -> CheckpointSerializer:
    """The serializer both document savers use unless given another."""
    return CheckpointSerializer()


class RedactingSerializer:
    """``serde`` that never writes a secret (``redact_secrets``); reads as ``serde``."""

    def __init__(self, serde: SerializerProtocol) -> None:
        self.serde = serde

    def dumps_typed(self, obj: Any) -> tuple[str, bytes]:
        return self.serde.dumps_typed(redact_secrets(obj))

    def loads_typed(self, data: tuple[str, bytes]) -> Any:
        return self.serde.loads_typed(data)


# --- retention ------------------------------------------------------------------------


class Retained(NamedTuple):
    """A stored checkpoint as retention sees it."""

    checkpoint_ns: str
    checkpoint_id: str
    # metadata["parents"][""]: the root checkpoint a subgraph step ran under.
    root_parent: str | None


def kept_checkpoints(
    stored: Iterable[Retained], keep_last: int
) -> frozenset[tuple[str, str]]:
    """The ``(checkpoint_ns, checkpoint_id)`` of one thread that retention keeps.

    The newest ``keep_last`` checkpoints of the root namespace, and the steps of
    the subgraphs they ran: a child namespace (one per subgraph task) is kept
    with the root checkpoint it ran under, so an interrupted subgraph still
    resumes. A namespace without that link (no ``parents`` in its metadata, or
    no root checkpoint at all) keeps its own newest ``keep_last``.
    """
    if keep_last < 1:
        raise ValueError("keep_last must be at least 1")
    stored = list(stored)
    roots = {s.checkpoint_id for s in stored if not s.checkpoint_ns}
    kept_roots = set(sorted(roots, reverse=True)[:keep_last])

    def linked(s: Retained) -> bool:
        return bool(kept_roots) and s.root_parent is not None

    unlinked: dict[str, set[str]] = {}
    for s in stored:
        if s.checkpoint_ns and not linked(s):
            unlinked.setdefault(s.checkpoint_ns, set()).add(s.checkpoint_id)
    newest = {
        ns: set(sorted(ids, reverse=True)[:keep_last]) for ns, ids in unlinked.items()
    }
    kept = set()
    for s in stored:
        if not s.checkpoint_ns:
            keep = s.checkpoint_id in kept_roots
        elif linked(s):
            keep = s.root_parent in kept_roots
        else:
            keep = s.checkpoint_id in newest[s.checkpoint_ns]
        if keep:
            kept.add((s.checkpoint_ns, s.checkpoint_id))
    return frozenset(kept)


# Value documents younger than this are never pruned: a turn writes its values
# before its checkpoint, so a run that started meanwhile may still need them.
RETENTION_GRACE = timedelta(minutes=1)


def created_before(created_at: datetime | str | None, cutoff: datetime) -> bool:
    """Whether a document's ``created_at`` (a datetime, or ISO text over RPC) is
    before ``cutoff``; unknown or unreadable is not (keep it). Naive is UTC."""
    if isinstance(created_at, str):
        try:
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError:
            return False
    if not isinstance(created_at, datetime):
        return False
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return created_at < cutoff


@dataclasses.dataclass
class RetentionReport:
    """What a prune of one thread kept and deleted (or would delete, dry run)."""

    thread_id: str
    keep_last: int
    applied: bool
    kept: int = 0  # checkpoints kept
    checkpoints: int = 0  # checkpoints deleted
    writes: int = 0  # pending writes deleted
    values: int = 0  # blobs, list items and parts deleted

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def _digest(*chunks: bytes) -> str:
    hasher = hashlib.sha256()
    for chunk in chunks:
        hasher.update(chunk)
    return hasher.hexdigest()


def collection_of(ref: str) -> str:
    """The collection holding the document a reference names."""
    return _REF_COLLECTIONS[ref[0]]


# --- reading: pure, never deserializes ------------------------------------------------


def references(data: Mapping[str, Any]) -> list[tuple[str, int]]:
    """References a stored document makes, with the bytes each may take."""
    found: list[tuple[str, int]] = []

    def stored(value: Any) -> None:
        if isinstance(value, Mapping) and "parts" in value:
            found.extend((ref, _STORED_BYTES) for ref in value["parts"])

    for name in ("checkpoint", "metadata", "value"):
        stored(data.get(name))
    for entry in (data.get("channels") or {}).values():
        if "blob" in entry:
            found.append((entry["blob"], _STORED_BYTES))
        else:
            stored(entry.get("value"))
    found.extend((ref, _CHUNK_BYTES) for ref in data.get("chunks") or ())
    found.extend(
        (ref, min(size, PART_SIZE) + DOCUMENT_OVERHEAD)
        for ref, size in data.get("elements") or ()
    )
    return found


def batches(refs: Iterable[tuple[str, int]]) -> list[tuple[str, list[str]]]:
    """Group references into reads of at most READ_BUDGET bytes each."""
    grouped: dict[str, list[tuple[str, int]]] = {}
    for ref, size in dict(refs).items():
        grouped.setdefault(collection_of(ref), []).append((ref, size))
    planned: list[tuple[str, list[str]]] = []
    for collection, members in grouped.items():
        batch: list[str] = []
        total = 0
        for ref, size in members:
            if batch and (total + size > READ_BUDGET or len(batch) >= MAX_IN_VALUES):
                planned.append((collection, batch))
                batch, total = [], 0
            batch.append(ref)
            total += size
        if batch:
            planned.append((collection, batch))
    return planned


def resolution(
    roots: Iterable[Mapping[str, Any]],
) -> Generator[tuple[str, list[str]], Iterable[Mapping[str, Any]], dict[str, Any]]:
    """Fetch what ``roots`` reference, level by level: blobs, chunks, elements, parts.

    Yields ``(collection, refs)`` to read; send back the documents found (any
    order). Returns every fetched document by ref. A missing one raises.
    """
    fetched: dict[str, Any] = {}
    pending = [r for d in roots for r in references(d)]
    while pending:
        found = []
        for collection, refs in batches(pending):
            for data in (yield collection, refs):
                fetched[data["ref"]] = data
                found.append(data)
        missing = sorted({ref for ref, _ in pending} - fetched.keys())
        if missing:
            raise ValueError(f"Checkpoint documents are missing: {missing[:5]}")
        pending = [r for d in found for r in references(d) if r[0] not in fetched]
    return fetched


def raw_value(stored: Mapping[str, Any], fetched: Mapping[str, Any]) -> dict[str, Any]:
    """A stored value as LangGraph's typed ``{"kind", "payload"}``, parts joined."""
    if "parts" not in stored:
        return {"kind": stored["kind"], "payload": stored["payload"]}
    payload = b"".join(fetched[ref]["payload"] for ref in stored["parts"])
    if len(payload) != stored["size"]:
        raise ValueError("A split value does not have its recorded size")
    return {"kind": stored["kind"], "payload": payload}


def raw_channel_values(
    data: Mapping[str, Any], fetched: Mapping[str, Any]
) -> dict[str, Any]:
    """Each channel's typed value; a list value is a list of typed elements."""
    values: dict[str, Any] = {}
    for channel, entry in (data.get("channels") or {}).items():
        if "value" in entry:
            values[channel] = raw_value(entry["value"], fetched)
            continue
        blob = fetched[entry["blob"]]
        if "value" in blob:
            values[channel] = raw_value(blob["value"], fetched)
        else:
            values[channel] = [
                raw_value(fetched[ref]["value"], fetched)
                for chunk in blob["chunks"]
                for ref, _ in fetched[chunk]["elements"]
            ]
    return values


# --- writing --------------------------------------------------------------------------


class Put(NamedTuple):
    collection: str
    key: str
    data: dict[str, Any]
    # 0: create-only. None: replace.
    if_version: int | None
    # On a create-only conflict: "keep" the stored document (content-addressed,
    # or a task's first write), or "compare" and accept only an identical one.
    on_conflict: Literal["keep", "compare"]


class Plan(NamedTuple):
    puts: list[Put]  # in order: what a document references comes before it
    config: RunnableConfig
    remember: tuple[tuple[str, str, str], Known]


class Known(NamedTuple):
    refs: frozenset[str]
    # channel -> (version, the checkpoint document's entry for it)
    channels: Mapping[str, tuple[Any, dict[str, Any]]]


class KnownReferences:
    """What checkpoints this saver loaded or wrote reference, so puts skip it.

    A child usually reuses its parent's entries and documents: a stored
    checkpoint's documents exist, and only ``delete_thread`` (with its runs
    stopped) removes them. Bounded, least recently used first out.
    """

    def __init__(self, capacity: int = 200_000) -> None:
        self._entries: OrderedDict[tuple[str, str, str], Known] = OrderedDict()
        self._size = 0
        self._capacity = capacity
        self._lock = threading.Lock()

    def remember(self, key: tuple[str, str, str], known: Known) -> None:
        with self._lock:
            previous = self._entries.pop(key, None)
            if previous is not None:
                self._size -= len(previous.refs)
            self._entries[key] = known
            self._size += len(known.refs)
            while self._size > self._capacity and len(self._entries) > 1:
                _, evicted = self._entries.popitem(last=False)
                self._size -= len(evicted.refs)

    def recall(
        self,
        thread_id: str,
        parent: tuple[str, str] | None,
        ancestors: Iterable[tuple[str, str]],
    ) -> Known:
        """References known for a child of ``parent`` (and of its ancestors)."""
        refs: set[str] = set()
        channels: Mapping[str, tuple[Any, dict[str, Any]]] = {}
        with self._lock:
            for position, (ns, checkpoint_id) in enumerate(
                [*([parent] if parent else []), *ancestors]
            ):
                known = self._entries.get((thread_id, ns, checkpoint_id))
                if known is None:
                    continue
                self._entries.move_to_end((thread_id, ns, checkpoint_id))
                refs |= known.refs
                if parent and position == 0:
                    channels = known.channels
        return Known(frozenset(refs), channels)

    def forget(self, thread_id: str) -> None:
        with self._lock:
            for key in [k for k in self._entries if k[0] == thread_id]:
                self._size -= len(self._entries.pop(key).refs)


class _Writer:
    """The documents one put adds, skipping what is known to be stored."""

    def __init__(self, schema: CheckpointDocuments, thread_id: str, known: Known):
        self.schema, self.thread_id, self.known = schema, thread_id, known
        self.refs: set[str] = set()
        self.planned: set[str] = set()
        self.parts: list[Put] = []
        self.elements: list[Put] = []
        self.chunks: list[Put] = []
        self.blobs: list[Put] = []

    def puts(self) -> list[Put]:
        return self.parts + self.elements + self.chunks + self.blobs

    def _add(self, bucket: list[Put], ref: str, body: dict[str, Any]) -> None:
        self.refs.add(ref)
        if ref in self.known.refs or ref in self.planned:
            return
        self.planned.add(ref)
        data = {
            "agent_id": self.schema.agent_id,
            "thread_id": self.thread_id,
            "ref": ref,
            "_schema": SCHEMA_VERSION,
        } | body
        key = self.schema.key(self.thread_id, ref)
        bucket.append(Put(collection_of(ref), key, data, 0, "keep"))

    def stored(self, typed: tuple[str, bytes]) -> dict[str, Any]:
        """A typed value as document data; above PART_SIZE, references to parts."""
        kind, payload = typed
        if len(payload) <= PART_SIZE:
            return {"kind": kind, "payload": payload}
        digest = _digest(payload)
        refs = []
        for index, start in enumerate(range(0, len(payload), PART_SIZE)):
            ref = f"p-{digest}.{index}"
            self._add(self.parts, ref, {"payload": payload[start : start + PART_SIZE]})
            refs.append(ref)
        return {"kind": kind, "size": len(payload), "parts": refs}

    def channel(self, value: Any) -> dict[str, Any]:
        """A changed channel's entry: inline when small, else a blob reference."""
        dumps = self.schema.serde.dumps_typed
        if type(value) is list:
            elements = [dumps(element) for element in value]
            if sum(len(payload) for _, payload in elements) > INLINE_LIMIT:
                return self._list(elements)
        typed = dumps(value)
        if len(typed[1]) <= INLINE_LIMIT:
            return {"value": {"kind": typed[0], "payload": typed[1]}}
        ref = "b-" + _digest(b"v", typed[0].encode(), b"\0", typed[1])
        if ref not in self.known.refs and ref not in self.planned:
            self._add(self.blobs, ref, {"value": self.stored(typed)})
        self.refs.add(ref)
        return {"blob": ref}

    def _list(self, elements: list[tuple[str, bytes]]) -> dict[str, Any]:
        entries = []
        for kind, payload in elements:
            ref = "e-" + _digest(kind.encode(), b"\0", payload)
            if ref not in self.known.refs and ref not in self.planned:
                self._add(self.elements, ref, {"value": self.stored((kind, payload))})
            self.refs.add(ref)
            entries.append([ref, len(payload)])
        chunks = []
        for start in range(0, len(entries), CHUNK_SIZE):
            chunk = entries[start : start + CHUNK_SIZE]
            ref = "c-" + _digest(json.dumps(chunk).encode())
            self._add(self.chunks, ref, {"elements": chunk})
            chunks.append(ref)
        ref = "b-" + _digest(b"l", json.dumps(chunks).encode())
        self._add(self.blobs, ref, {"chunks": chunks, "length": len(entries)})
        return {"blob": ref}


class CheckpointDocuments:
    """Document ids, write plans and decoding for one stable ``agent_id``.

    The document namespace, ``agent_id``, ``thread_id`` and ``checkpoint_ns``
    together isolate state; binding the namespace is the caller's concern.
    """

    def __init__(self, agent_id: str, serde: SerializerProtocol) -> None:
        if not agent_id:
            raise ValueError("agent_id must be a stable, nonempty identifier")
        self.agent_id = agent_id
        self.serde = RedactingSerializer(serde)
        self.known = KnownReferences()

    def key(self, *parts: Any) -> str:
        return hashlib.sha256(
            json.dumps([self.agent_id, *parts], ensure_ascii=True).encode()
        ).hexdigest()

    def load(self, value: Mapping[str, Any]) -> Any:
        return self.serde.loads_typed((value["kind"], value["payload"]))

    def retained(self, data: Mapping[str, Any], fetched: Mapping[str, Any]) -> Retained:
        """A checkpoint document (schema 1 or 2) as retention sees it; ``fetched``
        holds the parts of metadata stored in parts (``metadata_roots``)."""
        metadata = self.load(raw_value(data["metadata"], fetched))
        parents = metadata.get("parents") if isinstance(metadata, Mapping) else None
        root = parents.get("") if isinstance(parents, Mapping) else None
        return Retained(
            str(data["checkpoint_ns"]), str(data["checkpoint_id"]), root or None
        )

    @staticmethod
    def metadata_roots(data: Mapping[str, Any]) -> list[dict[str, Any]]:
        """What to resolve before ``retained``: the metadata, if split into parts."""
        metadata = data.get("metadata")
        return (
            [{"metadata": metadata}]
            if isinstance(metadata, Mapping) and "parts" in metadata
            else []
        )

    def scope(self, config: RunnableConfig) -> dict[str, str]:
        """Equality filters for the thread and checkpoint namespace ``config`` names."""
        configurable = config["configurable"]
        return {
            "agent_id": self.agent_id,
            "thread_id": configurable["thread_id"],
            "checkpoint_ns": configurable.get("checkpoint_ns", ""),
        }

    def thread_scope(self, thread_id: str) -> dict[str, str]:
        return {"agent_id": self.agent_id, "thread_id": thread_id}

    def history_scope(self, config: RunnableConfig | None) -> dict[str, str]:
        """Equality filters for ``list``: every thread, a thread, a namespace or one checkpoint."""
        scope = {"agent_id": self.agent_id}
        if config is None:
            return scope
        configurable = config["configurable"]
        scope["thread_id"] = configurable["thread_id"]
        if configurable.get("checkpoint_ns") is not None:
            scope["checkpoint_ns"] = configurable["checkpoint_ns"]
        if configurable.get("checkpoint_id"):
            scope["checkpoint_id"] = configurable["checkpoint_id"]
        return scope

    def checkpoint_key(self, config: RunnableConfig) -> str | None:
        """The id of the checkpoint ``config`` names, or None to ask for the latest."""
        checkpoint_id = config["configurable"].get("checkpoint_id")
        if not checkpoint_id:
            return None
        scope = self.scope(config)
        return self.key(scope["thread_id"], scope["checkpoint_ns"], checkpoint_id)

    def config(self, data: Mapping[str, Any]) -> RunnableConfig:
        return {
            "configurable": {
                k: data[k] for k in ("thread_id", "checkpoint_ns", "checkpoint_id")
            }
        }

    def pending_scope(self, data: Mapping[str, Any]) -> dict[str, str]:
        """Equality filters for the pending writes of checkpoint document ``data``."""
        if data.get("_schema") not in (1, SCHEMA_VERSION):
            raise ValueError("Unsupported checkpoint schema")
        return {name: data[name] for name in SCOPE_FIELDS}

    # --- writes ---------------------------------------------------------------------

    def checkpoint_plan(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
    ) -> Plan:
        """The documents a checkpoint adds; ``new_versions`` is not needed."""
        scope = self.scope(config)
        thread_id, ns = scope["thread_id"], scope["checkpoint_ns"]
        parent_id = config["configurable"].get("checkpoint_id")
        ancestors = list((metadata.get("parents") or {}).items())
        known = self.known.recall(
            thread_id, (ns, parent_id) if parent_id else None, ancestors
        )
        writer = _Writer(self, thread_id, known)
        versions = checkpoint["channel_versions"]
        channels: dict[str, dict[str, Any]] = {}
        remembered: dict[str, tuple[Any, dict[str, Any]]] = {}
        for channel, value in checkpoint["channel_values"].items():
            version = versions.get(channel)
            previous = known.channels.get(channel)
            if version is not None and previous is not None and previous[0] == version:
                entry = previous[1]  # unchanged since the parent: nothing to serialize
            else:
                entry = writer.channel(value)
            channels[channel] = entry
            if version is not None:
                remembered[channel] = (version, entry)
        stored = {k: v for k, v in checkpoint.items() if k != "channel_values"}
        data = scope | {
            "_schema": SCHEMA_VERSION,
            "checkpoint_id": checkpoint["id"],
            "parent_id": parent_id,
            "checkpoint": writer.stored(self.serde.dumps_typed(stored)),
            "metadata": writer.stored(
                self.serde.dumps_typed(get_checkpoint_metadata(config, metadata))
            ),
            "channels": channels,
        }
        key = self.key(thread_id, ns, checkpoint["id"])
        return Plan(
            [*writer.puts(), Put(CHECKPOINTS, key, data, 0, "compare")],
            self.config(data),
            (
                (thread_id, ns, checkpoint["id"]),
                Known(frozenset(known.refs | writer.refs), remembered),
            ),
        )

    def write_plan(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> list[Put]:
        """Pending writes, with the parts of large values first."""
        scope = self.scope(config)
        checkpoint_id = config["configurable"]["checkpoint_id"]
        writer = _Writer(self, scope["thread_id"], Known(frozenset(), {}))
        puts = []
        for position, (channel, value) in enumerate(writes):
            index = WRITES_IDX_MAP.get(channel, position)
            data = scope | {
                "_schema": SCHEMA_VERSION,
                "checkpoint_id": checkpoint_id,
                "task_id": task_id,
                "task_path": task_path,
                "index": index,
                "channel": channel,
                "value": writer.stored(self.serde.dumps_typed(value)),
            }
            key = self.key(
                scope["thread_id"],
                scope["checkpoint_ns"],
                checkpoint_id,
                task_id,
                index,
            )
            puts.append(Put(WRITES, key, data, 0 if index >= 0 else None, "keep"))
        return writer.puts() + puts

    # --- reads ----------------------------------------------------------------------

    def restore(
        self,
        data: Mapping[str, Any],
        writes: Sequence[Mapping[str, Any]],
        fetched: Mapping[str, Any],
    ) -> CheckpointTuple:
        """A checkpoint from its documents; later puts on it reuse what it references."""
        if data.get("_schema") == 1:
            return self._legacy(data, writes)
        self.pending_scope(data)
        checkpoint = self.load(raw_value(data["checkpoint"], fetched))
        values = raw_channel_values(data, fetched)
        checkpoint["channel_values"] = {
            channel: [self.load(v) for v in value]
            if isinstance(value, list)
            else self.load(value)
            for channel, value in values.items()
        }
        versions = checkpoint["channel_versions"]
        self.known.remember(
            (data["thread_id"], data["checkpoint_ns"], data["checkpoint_id"]),
            Known(
                frozenset(fetched),
                {
                    channel: (versions[channel], entry)
                    for channel, entry in data["channels"].items()
                    if channel in versions
                },
            ),
        )
        return self._tuple(data, checkpoint, writes, fetched)

    def _legacy(
        self, data: Mapping[str, Any], writes: Sequence[Mapping[str, Any]]
    ) -> CheckpointTuple:
        """Schema 1: the snapshot and every value inline."""
        return self._tuple(data, self.load(data["checkpoint"]), writes, {})

    def _tuple(
        self,
        data: Mapping[str, Any],
        checkpoint: Checkpoint,
        writes: Sequence[Mapping[str, Any]],
        fetched: Mapping[str, Any],
    ) -> CheckpointTuple:
        ordered = sorted(writes, key=lambda w: (w["task_id"], w["index"]))
        return CheckpointTuple(
            config=self.config(data),
            checkpoint=checkpoint,
            metadata=self.load(raw_value(data["metadata"], fetched)),
            parent_config=self.config(dict(data) | {"checkpoint_id": data["parent_id"]})
            if data["parent_id"]
            else None,
            pending_writes=[
                (w["task_id"], w["channel"], self.load(raw_value(w["value"], fetched)))
                for w in ordered
            ],
        )

    @staticmethod
    def matches(metadata: Mapping[str, Any], filter: dict[str, Any] | None) -> bool:
        """``list``'s metadata filter: every given key equal."""
        return not filter or all(metadata.get(k) == v for k, v in filter.items())
