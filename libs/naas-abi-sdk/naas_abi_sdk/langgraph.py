"""Async LangGraph 3.x checkpoint persistence through the document service.

Install naas-abi-sdk[langgraph]. Inject a namespace-bound DocumentClient. This
saver never connects to a database and never falls back to local memory.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator, Sequence
from typing import Any

from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    RunnableConfig,
    get_checkpoint_metadata,
)
from langgraph.checkpoint.serde.base import SerializerProtocol
from naas_abi_proto.document.v1 import document_pb2 as pb
from naas_abi_proto.document.values import decode_data, encode_data, encode_value

from naas_abi_sdk.document import DocumentClient
from naas_abi_sdk.transport import RPCError


class DocumentCheckpointSaver(BaseCheckpointSaver):
    """Use with graph.ainvoke/astream; one active run per agent/thread is required.

    agent_id is stable across replicas and distinct for different graphs. Module
    namespace, agent_id, thread_id and checkpoint_ns together isolate state.
    Call setup before running a graph. Transport/client lifetime belongs to the
    caller. Deleting a thread requires its runs to be stopped first.
    """

    CHECKPOINTS = "langgraph_checkpoints_v1"
    WRITES = "langgraph_writes_v1"

    def __init__(
        self,
        documents: DocumentClient,
        *,
        agent_id: str,
        serde: SerializerProtocol | None = None,
    ) -> None:
        super().__init__(serde=serde)
        if not agent_id:
            raise ValueError("agent_id must be a stable, nonempty identifier")
        self.documents = documents
        self.agent_id = agent_id

    async def setup(self) -> None:
        for name in (self.CHECKPOINTS, self.WRITES):
            await self.documents.ensure_collection(
                pb.EnsureCollectionRequest(
                    spec=pb.CollectionSpec(
                        name=name,
                        fields=[
                            pb.FieldSpec(name=f, type="string", indexed=True)
                            for f in (
                                "agent_id",
                                "thread_id",
                                "checkpoint_ns",
                                "checkpoint_id",
                            )
                        ],
                    )
                )
            )

    def _key(self, *parts: Any) -> str:
        return hashlib.sha256(
            json.dumps([self.agent_id, *parts], ensure_ascii=True).encode()
        ).hexdigest()

    def _scope(self, config) -> dict[str, str]:
        configurable = config["configurable"]
        return {
            "agent_id": self.agent_id,
            "thread_id": configurable["thread_id"],
            "checkpoint_ns": configurable.get("checkpoint_ns", ""),
        }

    def _config(self, data):
        return {
            "configurable": {
                k: data[k] for k in ("thread_id", "checkpoint_ns", "checkpoint_id")
            }
        }

    def _dump(self, value):
        kind, payload = self.serde.dumps_typed(value)
        return {"kind": kind, "payload": payload}

    def _load(self, value):
        return self.serde.loads_typed((value["kind"], value["payload"]))

    async def _scan(self, collection, scope, *, before=None):
        where = [
            pb.Predicate(field=k, operator="eq", value=encode_value(v))
            for k, v in scope.items()
        ]
        if before is not None:
            where.append(
                pb.Predicate(
                    field="checkpoint_id", operator="lt", value=encode_value(before)
                )
            )
        cursor = None
        while True:
            page = await self.documents.find(
                pb.FindRequest(
                    collection=collection,
                    where=where,
                    order_by=pb.OrderBy(field="checkpoint_id", direction="desc"),
                    limit=100,
                    cursor=cursor,
                )
            )
            for doc in page.items:
                yield doc
            if not page.HasField("cursor"):
                break
            cursor = page.cursor

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        data = self._scope(config) | {
            "_schema": 1,
            "checkpoint_id": checkpoint["id"],
            "parent_id": config["configurable"].get("checkpoint_id"),
            "checkpoint": self._dump(checkpoint),
            "metadata": self._dump(get_checkpoint_metadata(config, metadata)),
        }
        # A full checkpoint snapshot is one atomic document. Do not silently
        # overwrite an existing checkpoint ID with a divergent execution.
        key = self._key(data["thread_id"], data["checkpoint_ns"], checkpoint["id"])
        try:
            await self.documents.put(
                pb.PutRequest(
                    collection=self.CHECKPOINTS,
                    id=key,
                    data=encode_data(data),
                    if_version=0,
                )
            )
        except RPCError as exc:
            if exc.code != "VERSION_CONFLICT":
                raise
            existing = await self.documents.get(
                pb.GetRequest(collection=self.CHECKPOINTS, id=key)
            )
            if decode_data(existing.document.data) != data:
                raise
        return self._config(data)

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        scope = self._scope(config)
        checkpoint_id = config["configurable"]["checkpoint_id"]
        for index, (channel, value) in enumerate(writes):
            index = WRITES_IDX_MAP.get(channel, index)
            data = scope | {
                "_schema": 1,
                "checkpoint_id": checkpoint_id,
                "task_id": task_id,
                "task_path": task_path,
                "index": index,
                "channel": channel,
                "value": self._dump(value),
            }
            key = self._key(
                scope["thread_id"],
                scope["checkpoint_ns"],
                checkpoint_id,
                task_id,
                index,
            )
            try:
                await self.documents.put(
                    pb.PutRequest(
                        collection=self.WRITES,
                        id=key,
                        data=encode_data(data),
                        if_version=0 if index >= 0 else None,
                    )
                )
            except RPCError as exc:
                # Normal task writes are first-write-wins, matching LangGraph.
                # Special error/interrupt writes (negative indices) are updates.
                if index < 0 or exc.code != "VERSION_CONFLICT":
                    raise

    async def _tuple(self, document):
        data = decode_data(document.data)
        if data["_schema"] != 1:
            raise ValueError("Unsupported checkpoint schema")
        writes = [
            decode_data(d.data)
            async for d in self._scan(
                self.WRITES,
                {
                    k: data[k]
                    for k in ("agent_id", "thread_id", "checkpoint_ns", "checkpoint_id")
                },
            )
        ]
        writes.sort(key=lambda w: (w["task_id"], w["index"]))
        return CheckpointTuple(
            config=self._config(data),
            checkpoint=self._load(data["checkpoint"]),
            metadata=self._load(data["metadata"]),
            parent_config=self._config(data | {"checkpoint_id": data["parent_id"]})
            if data["parent_id"]
            else None,
            pending_writes=[
                (w["task_id"], w["channel"], self._load(w["value"])) for w in writes
            ],
        )

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        scope = self._scope(config)
        checkpoint_id = config["configurable"].get("checkpoint_id")
        if checkpoint_id:
            try:
                result = await self.documents.get(
                    pb.GetRequest(
                        collection=self.CHECKPOINTS,
                        id=self._key(
                            scope["thread_id"], scope["checkpoint_ns"], checkpoint_id
                        ),
                    )
                )
            except RPCError as exc:
                if exc.code == "DOCUMENT_NOT_FOUND":
                    return None
                raise
            return await self._tuple(result.document)
        async for document in self._scan(self.CHECKPOINTS, scope):
            return await self._tuple(document)
        return None

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        if limit is not None and limit <= 0:
            return
        scope = {"agent_id": self.agent_id}
        if config is not None:
            scope["thread_id"] = config["configurable"]["thread_id"]
            if "checkpoint_ns" in config["configurable"]:
                scope["checkpoint_ns"] = config["configurable"]["checkpoint_ns"]
        before_id = before["configurable"].get("checkpoint_id") if before else None
        count = 0
        async for document in self._scan(self.CHECKPOINTS, scope, before=before_id):
            result = await self._tuple(document)
            if filter and any(result.metadata.get(k) != v for k, v in filter.items()):
                continue
            yield result
            count += 1
            if limit is not None and count >= limit:
                break

    async def adelete_thread(self, thread_id: str) -> None:
        for collection in (self.WRITES, self.CHECKPOINTS):
            async for doc in self._scan(
                collection, {"agent_id": self.agent_id, "thread_id": thread_id}
            ):
                await self.documents.delete(
                    pb.DeleteRequest(
                        collection=collection, id=doc.id, if_version=doc.version
                    )
                )
