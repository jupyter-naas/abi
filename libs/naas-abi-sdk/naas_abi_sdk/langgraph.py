"""Async LangGraph 3.x checkpoint persistence through the document service.

Install naas-abi-sdk[langgraph]. Inject a namespace-bound DocumentClient. This
saver never connects to a database and never falls back to local memory.
Documents follow ``naas_abi_sdk.langgraph_documents`` (schema 2: each step
stores what changed, no document or read exceeds a fixed size), shared with the
engine's synchronous saver in naas_abi_core.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any

from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    RunnableConfig,
)
from langgraph.checkpoint.serde.base import SerializerProtocol
from naas_abi_proto.document.v1 import document_pb2 as pb
from naas_abi_proto.document.values import decode_data, encode_data, encode_value

from naas_abi_sdk.document import DocumentClient
from naas_abi_sdk.langgraph_documents import (
    BLOBS,
    CHECKPOINT_PAGE,
    CHECKPOINTS,
    COLLECTIONS,
    ITEMS,
    LEGACY_CHECKPOINTS,
    LEGACY_PAGE,
    LEGACY_WRITES,
    NEWEST_FIRST,
    PARTS,
    RETENTION_GRACE,
    WRITE_PAGE,
    WRITES,
    CheckpointDocuments,
    Put,
    Retained,
    RetentionReport,
    created_before,
    kept_checkpoints,
    next_version,
    resolution,
)
from naas_abi_sdk.services.document import DocumentService
from naas_abi_sdk.transport import RPCError

_LEGACY = (LEGACY_CHECKPOINTS, LEGACY_WRITES)


class DocumentCheckpointSaver(BaseCheckpointSaver):
    """Use with graph.ainvoke/astream; one active run per agent/thread is required.

    agent_id is stable across replicas and distinct for different graphs. Module
    namespace, agent_id, thread_id and checkpoint_ns together isolate state.
    Call setup before running a graph. Transport/client lifetime belongs to the
    caller. Deleting a thread requires its runs to be stopped first. With
    ``legacy_reads``, threads without schema 2 checkpoints are read from schema 1
    and continue in schema 2.
    """

    CHECKPOINTS = CHECKPOINTS
    WRITES = WRITES

    def __init__(
        self,
        documents: DocumentClient | DocumentService,
        *,
        agent_id: str,
        serde: SerializerProtocol | None = None,
        legacy_reads: bool = True,
    ) -> None:
        super().__init__(serde=serde)
        self.schema = CheckpointDocuments(agent_id, self.serde)
        self.documents = (
            documents.rpc if isinstance(documents, DocumentService) else documents
        )
        self.agent_id = agent_id
        self.legacy_reads = legacy_reads

    async def setup(self) -> None:
        for name, fields in COLLECTIONS.items():
            await self.documents.ensure_collection(
                pb.EnsureCollectionRequest(
                    spec=pb.CollectionSpec(
                        name=name,
                        fields=[
                            pb.FieldSpec(name=f, type="string", indexed=True)
                            for f in fields
                        ],
                    )
                )
            )

    def _key(self, *parts: Any) -> str:
        return self.schema.key(*parts)

    def get_next_version(self, current: Any, channel: None) -> Any:
        return next_version(current)

    # --- storage --------------------------------------------------------------------

    async def _scan(self, collection, scope, *, before=None, page):
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
        field, direction = NEWEST_FIRST
        cursor = None
        while True:
            try:
                result = await self.documents.find(
                    pb.FindRequest(
                        collection=collection,
                        where=where,
                        order_by=pb.OrderBy(field=field, direction=direction),
                        limit=page,
                        cursor=cursor,
                    )
                )
            except RPCError as exc:
                if exc.code == "COLLECTION_NOT_FOUND" and collection in _LEGACY:
                    return
                raise
            for doc in result.items:
                yield doc
            if not result.HasField("cursor"):
                break
            cursor = result.cursor

    async def _legacy_scan(self, scope, *, before=None):
        if self.legacy_reads:
            async for doc in self._scan(
                LEGACY_CHECKPOINTS, scope, before=before, page=LEGACY_PAGE
            ):
                yield doc

    async def _put(self, put: Put) -> None:
        try:
            await self.documents.put(
                pb.PutRequest(
                    collection=put.collection,
                    id=put.key,
                    data=encode_data(put.data),
                    if_version=put.if_version,
                )
            )
        except RPCError as exc:
            if exc.code != "VERSION_CONFLICT":
                raise
            # "keep": content-addressed, or a task's first write wins. "compare":
            # do not silently overwrite a checkpoint ID with a divergent execution.
            if put.on_conflict == "compare":
                existing = await self.documents.get(
                    pb.GetRequest(collection=put.collection, id=put.key)
                )
                if decode_data(existing.document.data) != put.data:
                    raise

    async def _get(self, collection: str, key: str) -> dict[str, Any] | None:
        try:
            result = await self.documents.get(
                pb.GetRequest(collection=collection, id=key)
            )
        except RPCError as exc:
            if exc.code in ("DOCUMENT_NOT_FOUND", "COLLECTION_NOT_FOUND"):
                return None
            raise
        return decode_data(result.document.data)

    async def _fetch(self, thread_id: str, collection: str, refs: list[str]):
        where = [
            pb.Predicate(
                field="agent_id", operator="eq", value=encode_value(self.agent_id)
            ),
            pb.Predicate(
                field="thread_id", operator="eq", value=encode_value(thread_id)
            ),
            pb.Predicate(field="ref", operator="in", value=encode_value(refs)),
        ]
        found: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:  # every page: one can be cut short by the engine's byte budget
            result = await self.documents.find(
                pb.FindRequest(
                    collection=collection, where=where, limit=len(refs), cursor=cursor
                )
            )
            found.extend(decode_data(doc.data) for doc in result.items)
            if not result.HasField("cursor"):
                return found
            cursor = result.cursor

    async def _resolve(
        self, thread_id: str, roots: Sequence[Mapping[str, Any]]
    ) -> dict[str, Any]:
        """Every document ``roots`` reference, by ref, read in bounded batches."""
        flow = resolution(roots)
        try:
            collection, refs = next(flow)
            while True:
                collection, refs = flow.send(
                    await self._fetch(thread_id, collection, refs)
                )
        except StopIteration as done:
            return done.value

    async def _writes(self, data: Mapping[str, Any]) -> list[dict[str, Any]]:
        legacy = data.get("_schema") == 1
        return [
            decode_data(d.data)
            async for d in self._scan(
                LEGACY_WRITES if legacy else self.WRITES,
                self.schema.pending_scope(data),
                page=LEGACY_PAGE if legacy else WRITE_PAGE,
            )
        ]

    async def _load(self, data: Mapping[str, Any]) -> CheckpointTuple:
        writes = await self._writes(data)
        fetched: dict[str, Any] = {}
        if data.get("_schema") != 1:
            fetched = await self._resolve(data["thread_id"], [data, *writes])
        return self.schema.restore(data, writes, fetched)

    # --- LangGraph ------------------------------------------------------------------

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        plan = self.schema.checkpoint_plan(config, checkpoint, metadata)
        for put in plan.puts:
            await self._put(put)
        self.schema.known.remember(*plan.remember)
        return plan.config

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        for put in self.schema.write_plan(config, writes, task_id, task_path):
            await self._put(put)

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        key = self.schema.checkpoint_key(config)
        if key is not None:
            data = await self._get(self.CHECKPOINTS, key)
            if data is None and self.legacy_reads:
                data = await self._get(LEGACY_CHECKPOINTS, key)
            return None if data is None else await self._load(data)
        # The latest only: every turn starts here, so never read a full page.
        scope = self.schema.scope(config)
        async for document in self._scan(self.CHECKPOINTS, scope, page=1):
            return await self._load(decode_data(document.data))
        async for document in self._legacy_scan(scope):
            return await self._load(decode_data(document.data))
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
        before_id = before["configurable"].get("checkpoint_id") if before else None
        scope = self.schema.history_scope(config)
        count = 0
        # Schema 2 then schema 1: a continued thread's newer steps come first.
        for documents in (
            self._scan(self.CHECKPOINTS, scope, before=before_id, page=CHECKPOINT_PAGE),
            self._legacy_scan(scope, before=before_id),
        ):
            async for document in documents:
                result = await self._load(decode_data(document.data))
                if not self.schema.matches(result.metadata, filter):
                    continue
                yield result
                count += 1
                if limit is not None and count >= limit:
                    return

    async def adelete_thread(self, thread_id: str) -> None:
        # Checkpoints first: a failure part-way leaves unreferenced documents
        # (invisible, removed by a retry), never a checkpoint missing its values.
        self.schema.known.forget(thread_id)
        scope = self.schema.thread_scope(thread_id)
        for collection in (
            self.CHECKPOINTS,
            LEGACY_CHECKPOINTS,
            *(c for c in COLLECTIONS if c != self.CHECKPOINTS),
            LEGACY_WRITES,
        ):
            async for doc in self._scan(collection, scope, page=WRITE_PAGE):
                await self.documents.delete(
                    pb.DeleteRequest(
                        collection=collection, id=doc.id, if_version=doc.version
                    )
                )

    # --- retention --------------------------------------------------------------------

    async def athread_ids(self) -> list[str]:
        """Every thread with checkpoints in this scope, schema 2 or 1."""
        scope = {"agent_id": self.agent_id}
        found: set[str] = set()
        for collection, page in (
            (self.CHECKPOINTS, CHECKPOINT_PAGE),
            (LEGACY_CHECKPOINTS, LEGACY_PAGE),
        ):
            async for doc in self._scan(collection, scope, page=page):
                found.add(str(decode_data(doc.data)["thread_id"]))
        return sorted(found)

    async def aprune(
        self,
        thread_id: str,
        *,
        keep_last: int,
        apply: bool = True,
        grace: timedelta = RETENTION_GRACE,
    ) -> RetentionReport:
        """Keep a thread's newest ``keep_last`` checkpoints, and the subgraph steps
        they ran (``kept_checkpoints``); delete the older ones (schema 2 and 1),
        their pending writes, and every value document no kept checkpoint or
        write references. Values created within ``grace`` are kept. Stop the
        thread's runs first, as for ``adelete_thread``. ``apply=False`` counts.

        Nothing is deleted until what the kept checkpoints reference is known,
        then checkpoints go first: a failure part-way leaves unreferenced
        documents (removed by a retry), never a checkpoint missing its values.
        """
        if keep_last < 1:
            raise ValueError("keep_last must be at least 1")
        cutoff = datetime.now(timezone.utc) - grace
        report = RetentionReport(thread_id, keep_last, apply)
        scope = self.schema.thread_scope(thread_id)
        stored: list[tuple[str, str, int, Retained]] = []
        for collection, page in (
            (self.CHECKPOINTS, CHECKPOINT_PAGE),
            (LEGACY_CHECKPOINTS, LEGACY_PAGE),
        ):
            async for doc in self._scan(collection, scope, page=page):
                data = decode_data(doc.data)
                fetched = await self._resolve(
                    thread_id, self.schema.metadata_roots(data)
                )
                retained = self.schema.retained(data, fetched)
                stored.append((collection, doc.id, doc.version, retained))
        kept = kept_checkpoints((r for *_, r in stored), keep_last)
        report.kept = len(kept)
        live: set[str] = set()
        for collection, key, _, retained in stored:
            point = (retained.checkpoint_ns, retained.checkpoint_id)
            if point in kept and collection == self.CHECKPOINTS:
                checkpoint = await self._get(collection, key)
                if checkpoint is not None:
                    writes = await self._writes(checkpoint)
                    live |= set(await self._resolve(thread_id, [checkpoint, *writes]))
        pruned = {(r.checkpoint_ns, r.checkpoint_id) for *_, r in stored} - kept
        self.schema.known.forget(thread_id)
        for collection, key, version, retained in stored:
            if (retained.checkpoint_ns, retained.checkpoint_id) in pruned:
                report.checkpoints += await self._drop(apply, collection, key, version)
        for collection in (self.WRITES, LEGACY_WRITES):
            async for doc in self._scan(collection, scope, page=WRITE_PAGE):
                data = decode_data(doc.data)
                if (data["checkpoint_ns"], data["checkpoint_id"]) in pruned:
                    report.writes += await self._drop(
                        apply, collection, doc.id, doc.version
                    )
        for collection in (BLOBS, ITEMS, PARTS):
            async for doc in self._scan(collection, scope, page=WRITE_PAGE):
                data = decode_data(doc.data)
                if data["ref"] not in live and created_before(doc.created_at, cutoff):
                    report.values += await self._drop(
                        apply, collection, doc.id, doc.version
                    )
        return report

    async def _drop(self, apply: bool, collection: str, key: str, version: int) -> int:
        """1 when the document is (or, in a dry run, would be) deleted."""
        if not apply:
            return 1
        try:
            await self.documents.delete(
                pb.DeleteRequest(collection=collection, id=key, if_version=version)
            )
        except RPCError as exc:
            if exc.code in (
                "DOCUMENT_NOT_FOUND",
                "VERSION_CONFLICT",
                "COLLECTION_NOT_FOUND",
            ):
                return 0  # already gone, or changed since it was read: leave it
            raise
        return 1
