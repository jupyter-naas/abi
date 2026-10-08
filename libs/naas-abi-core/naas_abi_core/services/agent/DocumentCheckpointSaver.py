"""LangGraph checkpoints of engine-hosted agents, kept in the Document Service.

The synchronous twin of ``naas_abi_sdk.langgraph.DocumentCheckpointSaver``:
both plan writes and decode reads through ``naas_abi_sdk.langgraph_documents``,
so documents are identical and a thread moves between an engine agent and an
SDK agent unchanged. Each step stores only what changed; reads fetch by
reference in bounded batches. Needs naas-abi-sdk (installed by the [nats] extra).
"""

from __future__ import annotations

import asyncio
import itertools
from collections.abc import AsyncIterator, Iterator, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
from langgraph.checkpoint.serde.base import SerializerProtocol
from naas_abi_core.services.document.DocumentPort import (
    CollectionNotFound,
    CollectionSpec,
    Document,
    DocumentNotFound,
    FieldSpec,
    Predicate,
    Value,
    VersionConflict,
)
from naas_abi_core.services.document.DocumentService import DocumentService
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

# Engine-hosted agents share one checkpoint scope, as they shared the process-wide
# PostgresSaver: a thread (a Nexus conversation, an OpenAI-gateway chat) keeps its
# history when the user switches agents, and sub-agents always ran inside their
# supervisor's graph and checkpointer. Remote SDK agents keep their own module
# namespace and agent_id (naas_abi_sdk.agents.hosting.agent_memory_id).
ENGINE_MEMORY_NAMESPACE = "naas_abi_core.services.agent"
ENGINE_MEMORY_ID = "engine.v1"
# Documents of one thread deleted per query; any one may hold PART_SIZE bytes.
DELETE_PAGE = WRITE_PAGE


class DocumentCheckpointSaver(BaseCheckpointSaver):
    """Checkpoints in a namespace-bound ``DocumentService``; sync and async graphs.

    Writes schema 2 (increments). With ``legacy_reads``, threads without schema
    2 checkpoints are read from schema 1 (``*_v1``) and continue in schema 2.
    The async methods run the synchronous ones in a worker thread: storage calls
    block, and a NATS-backed document adapter must not be called from the event
    loop that serves it. Concurrent turns on one thread fork from the same parent
    and the newest checkpoint becomes the head, as with LangGraph's own savers;
    a checkpoint document is never overwritten with different state.
    """

    def __init__(
        self,
        documents: DocumentService,
        *,
        agent_id: str,
        serde: SerializerProtocol | None = None,
        legacy_reads: bool = True,
    ) -> None:
        super().__init__(serde=serde)
        self.schema = CheckpointDocuments(agent_id, self.serde)
        self.documents = documents
        self.agent_id = agent_id
        self.legacy_reads = legacy_reads

    @classmethod
    def for_engine(cls, root: DocumentService) -> DocumentCheckpointSaver:
        """The saver every engine-hosted agent shares, its collections ensured."""
        saver = cls(
            root.for_namespace(ENGINE_MEMORY_NAMESPACE), agent_id=ENGINE_MEMORY_ID
        )
        saver.setup()
        return saver

    def setup(self) -> None:
        for collection, names in COLLECTIONS.items():
            fields = tuple(
                FieldSpec(name=n, type="string", indexed=True) for n in names
            )
            self.documents.ensure_collection(
                CollectionSpec(name=collection, fields=fields)
            )

    def get_next_version(self, current: Any, channel: None) -> Any:
        return next_version(current)

    # --- storage --------------------------------------------------------------------

    def _scan(
        self,
        collection: str,
        scope: Mapping[str, str],
        *,
        before: str | None = None,
        page: int,
    ) -> Iterator[Document]:
        where: list[Predicate] = [(name, "eq", value) for name, value in scope.items()]
        if before is not None:
            where.append(("checkpoint_id", "lt", before))
        try:
            yield from self.documents.iterate(
                collection, where=where, order_by=NEWEST_FIRST, batch=page
            )
        except CollectionNotFound:
            if collection not in (LEGACY_CHECKPOINTS, LEGACY_WRITES):
                raise

    def _legacy_scan(
        self, scope: Mapping[str, str], *, before: str | None = None
    ) -> Iterator[Document]:
        if self.legacy_reads:
            yield from self._scan(
                LEGACY_CHECKPOINTS, scope, before=before, page=LEGACY_PAGE
            )

    def _put(self, put: Put) -> None:
        try:
            self.documents.put(
                put.collection, put.key, put.data, if_version=put.if_version
            )
        except VersionConflict:
            # "keep": content-addressed, or a task's first write wins. "compare":
            # a repeated call may store the same checkpoint again; different
            # state under an existing checkpoint ID is a divergent execution.
            if put.on_conflict == "compare" and (
                self.documents.get(put.collection, put.key).data != put.data
            ):
                raise

    def _fetch(self, thread_id: str, collection: str, refs: list[str]) -> list[Any]:
        wanted: list[Value] = [*refs]
        # Every page: one can be cut short by the engine's byte budget.
        return [
            document.data
            for document in self.documents.iterate(
                collection,
                where=[
                    ("agent_id", "eq", self.agent_id),
                    ("thread_id", "eq", thread_id),
                    ("ref", "in", wanted),
                ],
                batch=len(refs),
            )
        ]

    def _resolve(
        self, thread_id: str, roots: Sequence[Mapping[str, Any]]
    ) -> dict[str, Any]:
        """Every document ``roots`` reference, by ref, read in bounded batches."""
        flow = resolution(roots)
        try:
            collection, refs = next(flow)
            while True:
                collection, refs = flow.send(self._fetch(thread_id, collection, refs))
        except StopIteration as done:
            return done.value

    def _writes(self, data: Mapping[str, Any]) -> list[dict[str, Any]]:
        legacy = data.get("_schema") == 1
        return [
            document.data
            for document in self._scan(
                LEGACY_WRITES if legacy else WRITES,
                self.schema.pending_scope(data),
                page=LEGACY_PAGE if legacy else WRITE_PAGE,
            )
        ]

    def _load(self, data: dict[str, Any]) -> CheckpointTuple:
        writes = self._writes(data)
        fetched: dict[str, Any] = {}
        if data.get("_schema") != 1:
            fetched = self._resolve(data["thread_id"], [data, *writes])
        return self.schema.restore(data, writes, fetched)

    def _get(self, collection: str, key: str) -> dict[str, Any] | None:
        try:
            return self.documents.get(collection, key).data
        except (DocumentNotFound, CollectionNotFound):
            return None

    # --- LangGraph ------------------------------------------------------------------

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        key = self.schema.checkpoint_key(config)
        if key is not None:
            data = self._get(CHECKPOINTS, key)
            if data is None and self.legacy_reads:
                data = self._get(LEGACY_CHECKPOINTS, key)
            return None if data is None else self._load(data)
        # The latest only: every turn starts here, so never read a full page.
        scope = self.schema.scope(config)
        latest = itertools.chain(
            self._scan(CHECKPOINTS, scope, page=1), self._legacy_scan(scope)
        )
        for document in latest:
            return self._load(document.data)
        return None

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        plan = self.schema.checkpoint_plan(config, checkpoint, metadata)
        for put in plan.puts:
            self._put(put)
        self.schema.known.remember(*plan.remember)
        return plan.config

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        for put in self.schema.write_plan(config, writes, task_id, task_path):
            self._put(put)

    def delete_thread(self, thread_id: str) -> None:
        # Checkpoints first: a failure part-way leaves unreferenced documents
        # (invisible, removed by a retry), never a checkpoint missing its values.
        self.schema.known.forget(thread_id)
        scope = self.schema.thread_scope(thread_id)
        for collection in (
            CHECKPOINTS,
            LEGACY_CHECKPOINTS,
            *(c for c in COLLECTIONS if c != CHECKPOINTS),
            LEGACY_WRITES,
        ):
            for document in self._scan(collection, scope, page=DELETE_PAGE):
                self.documents.delete(
                    collection, document.id, if_version=document.version
                )

    def list(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        if limit is not None and limit <= 0:
            return
        before_id = before["configurable"].get("checkpoint_id") if before else None
        scope = self.schema.history_scope(config)
        # Schema 2 then schema 1: a continued thread's newer steps come first.
        documents = itertools.chain(
            self._scan(CHECKPOINTS, scope, before=before_id, page=CHECKPOINT_PAGE),
            self._legacy_scan(scope, before=before_id),
        )
        count = 0
        for document in documents:
            result = self._load(document.data)
            if not self.schema.matches(result.metadata, filter):
                continue
            yield result
            count += 1
            if limit is not None and count >= limit:
                return

    # --- retention --------------------------------------------------------------------

    def thread_ids(self) -> Sequence[str]:
        """Every thread with checkpoints in this scope, schema 2 or 1."""
        scope = {"agent_id": self.agent_id}
        return sorted(
            {
                str(document.data["thread_id"])
                for collection, page in (
                    (CHECKPOINTS, CHECKPOINT_PAGE),
                    (LEGACY_CHECKPOINTS, LEGACY_PAGE),
                )
                for document in self._scan(collection, scope, page=page)
            }
        )

    def prune(
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
        thread's runs first, as for ``delete_thread``. ``apply=False`` counts.

        Nothing is deleted until what the kept checkpoints reference is known,
        then checkpoints go first: a failure part-way leaves unreferenced
        documents (removed by a retry), never a checkpoint missing its values.
        """
        if keep_last < 1:
            raise ValueError("keep_last must be at least 1")
        cutoff = datetime.now(UTC) - grace
        report = RetentionReport(thread_id, keep_last, apply)
        scope = self.schema.thread_scope(thread_id)
        stored: list[tuple[str, str, int, Retained]] = []
        for collection, page in (
            (CHECKPOINTS, CHECKPOINT_PAGE),
            (LEGACY_CHECKPOINTS, LEGACY_PAGE),
        ):
            for document in self._scan(collection, scope, page=page):
                fetched = self._resolve(
                    thread_id, self.schema.metadata_roots(document.data)
                )
                retained = self.schema.retained(document.data, fetched)
                stored.append((collection, document.id, document.version, retained))
        kept = kept_checkpoints((r for *_, r in stored), keep_last)
        report.kept = len(kept)
        live: set[str] = set()
        for collection, key, _, retained in stored:
            point = (retained.checkpoint_ns, retained.checkpoint_id)
            if point in kept and collection == CHECKPOINTS:
                data = self._get(collection, key)
                if data is not None:
                    live |= set(self._resolve(thread_id, [data, *self._writes(data)]))
        pruned = {(r.checkpoint_ns, r.checkpoint_id) for *_, r in stored} - kept
        self.schema.known.forget(thread_id)
        for collection, key, version, retained in stored:
            if (retained.checkpoint_ns, retained.checkpoint_id) in pruned:
                report.checkpoints += self._drop(apply, collection, key, version)
        for collection in (WRITES, LEGACY_WRITES):
            for document in self._scan(collection, scope, page=DELETE_PAGE):
                data = document.data
                if (data["checkpoint_ns"], data["checkpoint_id"]) in pruned:
                    report.writes += self._drop(
                        apply, collection, document.id, document.version
                    )
        for collection in (BLOBS, ITEMS, PARTS):
            for document in self._scan(collection, scope, page=DELETE_PAGE):
                if document.data["ref"] not in live and created_before(
                    document.created_at, cutoff
                ):
                    report.values += self._drop(
                        apply, collection, document.id, document.version
                    )
        return report

    def _drop(self, apply: bool, collection: str, key: str, version: int) -> int:
        """1 when the document is (or, in a dry run, would be) deleted."""
        if not apply:
            return 1
        try:
            self.documents.delete(collection, key, if_version=version)
        except (DocumentNotFound, VersionConflict, CollectionNotFound):
            return 0  # already gone, or changed since it was read: leave it
        return 1

    # --- migration support ------------------------------------------------------------

    def contains(self, config: RunnableConfig) -> bool:
        """Whether the checkpoint ``config`` names is stored in schema 2."""
        key = self.schema.checkpoint_key(config)
        return key is not None and self._get(CHECKPOINTS, key) is not None

    def lineage(self, thread_id: str) -> tuple[str, str | None] | None:
        """The schema 2 head of a thread's root namespace, and the parent its
        schema 2 history starts from (None for a thread started in schema 2)."""
        scope = self.schema.thread_scope(thread_id) | {"checkpoint_ns": ""}
        head = next(self._scan(CHECKPOINTS, scope, page=1), None)
        if head is None:
            return None
        parent: Any = head.data["parent_id"]
        while parent:
            data = self._get(CHECKPOINTS, self.schema.key(thread_id, "", parent))
            if data is None:
                break
            parent = data["parent_id"]
        return str(head.data["checkpoint_id"]), parent

    # --- async API ------------------------------------------------------------------

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        return await asyncio.to_thread(self.get_tuple, config)

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        return await asyncio.to_thread(
            self.put, config, checkpoint, metadata, new_versions
        )

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        await asyncio.to_thread(self.put_writes, config, writes, task_id, task_path)

    async def adelete_thread(self, thread_id: str) -> None:
        await asyncio.to_thread(self.delete_thread, thread_id)

    async def athread_ids(self) -> Sequence[str]:
        return await asyncio.to_thread(self.thread_ids)

    async def aprune(
        self,
        thread_id: str,
        *,
        keep_last: int,
        apply: bool = True,
        grace: timedelta = RETENTION_GRACE,
    ) -> RetentionReport:
        return await asyncio.to_thread(
            lambda: self.prune(thread_id, keep_last=keep_last, apply=apply, grace=grace)
        )

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        results = self.list(config, filter=filter, before=before, limit=limit)
        while (result := await asyncio.to_thread(next, results, None)) is not None:
            yield result


class LegacyDocumentCheckpointReader(DocumentCheckpointSaver):
    """Schema 1 only, read-only: the source of a v1 to v2 migration."""

    def __init__(self, documents: DocumentService, *, agent_id: str) -> None:
        super().__init__(documents, agent_id=agent_id)

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        key = self.schema.checkpoint_key(config)
        if key is not None:
            data = self._get(LEGACY_CHECKPOINTS, key)
            return None if data is None else self._load(data)
        for document in self._legacy_scan(self.schema.scope(config)):
            return self._load(document.data)
        return None

    def list(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        if limit is not None and limit <= 0:
            return
        before_id = before["configurable"].get("checkpoint_id") if before else None
        documents = self._legacy_scan(
            self.schema.history_scope(config), before=before_id
        )
        results = (self._load(d.data) for d in documents)
        matching = (r for r in results if self.schema.matches(r.metadata, filter))
        yield from itertools.islice(matching, limit)

    def thread_ids(self) -> Sequence[str]:
        scope = {"agent_id": self.agent_id}
        return sorted({str(d.data["thread_id"]) for d in self._legacy_scan(scope)})

    def put(self, *args: Any, **kwargs: Any) -> RunnableConfig:
        raise NotImplementedError("Schema 1 checkpoints are read-only")

    def put_writes(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError("Schema 1 checkpoints are read-only")

    def delete_thread(self, thread_id: str) -> None:
        raise NotImplementedError("Schema 1 checkpoints are read-only")

    def prune(self, *args: Any, **kwargs: Any) -> RetentionReport:
        raise NotImplementedError("Schema 1 checkpoints are read-only")
