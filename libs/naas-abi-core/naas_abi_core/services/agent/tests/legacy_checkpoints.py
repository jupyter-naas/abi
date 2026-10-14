"""Schema 1 checkpoint documents (full snapshots), as savers wrote them until v2.

Savers only read this format now; tests write it to cover the fallback and the
v1 to v2 migration.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from langgraph.checkpoint.base import WRITES_IDX_MAP, get_checkpoint_metadata
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from naas_abi_core.services.document.DocumentPort import CollectionSpec, FieldSpec
from naas_abi_core.services.document.DocumentService import DocumentService
from naas_abi_sdk.langgraph_documents import (
    LEGACY_CHECKPOINTS,
    LEGACY_WRITES,
    SCOPE_FIELDS,
)

_serde = JsonPlusSerializer()


def _key(agent_id: str, *parts: Any) -> str:
    return hashlib.sha256(
        json.dumps([agent_id, *parts], ensure_ascii=True).encode()
    ).hexdigest()


def _dump(value: Any) -> dict[str, Any]:
    kind, payload = _serde.dumps_typed(value)
    return {"kind": kind, "payload": payload}


def setup_v1(documents: DocumentService) -> None:
    fields = tuple(FieldSpec(name=f, type="string", indexed=True) for f in SCOPE_FIELDS)
    for collection in (LEGACY_CHECKPOINTS, LEGACY_WRITES):
        documents.ensure_collection(CollectionSpec(name=collection, fields=fields))


def put_v1(documents, agent_id, config, checkpoint, metadata) -> dict[str, Any]:
    configurable = config["configurable"]
    scope = {
        "agent_id": agent_id,
        "thread_id": configurable["thread_id"],
        "checkpoint_ns": configurable.get("checkpoint_ns", ""),
    }
    data = scope | {
        "_schema": 1,
        "checkpoint_id": checkpoint["id"],
        "parent_id": configurable.get("checkpoint_id"),
        "checkpoint": _dump(checkpoint),
        "metadata": _dump(get_checkpoint_metadata(config, metadata)),
    }
    key = _key(agent_id, scope["thread_id"], scope["checkpoint_ns"], checkpoint["id"])
    documents.put(LEGACY_CHECKPOINTS, key, data)
    return {
        "configurable": {
            "thread_id": scope["thread_id"],
            "checkpoint_ns": scope["checkpoint_ns"],
            "checkpoint_id": checkpoint["id"],
        }
    }


def put_writes_v1(documents, agent_id, config, writes, task_id) -> None:
    configurable = config["configurable"]
    for position, (channel, value) in enumerate(writes):
        index = WRITES_IDX_MAP.get(channel, position)
        data = {
            "agent_id": agent_id,
            "thread_id": configurable["thread_id"],
            "checkpoint_ns": configurable.get("checkpoint_ns", ""),
            "_schema": 1,
            "checkpoint_id": configurable["checkpoint_id"],
            "task_id": task_id,
            "task_path": "",
            "index": index,
            "channel": channel,
            "value": _dump(value),
        }
        key = _key(
            agent_id,
            data["thread_id"],
            data["checkpoint_ns"],
            data["checkpoint_id"],
            task_id,
            index,
        )
        documents.put(LEGACY_WRITES, key, data)


def v1_saver(documents: DocumentService, agent_id: str) -> Any:
    """An InMemorySaver that also stores what it is given as schema 1 documents.

    Integer versions, as the schema 1 SDK saver used.
    """
    from langgraph.checkpoint.memory import InMemorySaver

    setup_v1(documents)

    class V1Saver(InMemorySaver):
        def put(self, config, checkpoint, metadata, new_versions):
            put_v1(documents, agent_id, config, checkpoint, metadata)
            return super().put(config, checkpoint, metadata, new_versions)

        def put_writes(self, config, writes, task_id, task_path=""):
            put_writes_v1(documents, agent_id, config, writes, task_id)
            super().put_writes(config, writes, task_id, task_path)

        def get_next_version(self, current, channel):
            return 1 if current is None else current + 1

    return V1Saver()
