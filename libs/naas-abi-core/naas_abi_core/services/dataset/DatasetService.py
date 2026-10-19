from __future__ import annotations

# ``list`` is a port method name, so it shadows the builtin for annotations
# evaluated in the class bodies below; use ``builtins.list`` there.
import builtins
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from typing import Any

from naas_abi_core import logger
from naas_abi_core.services.dataset.DatasetPort import (
    DatasetInfo,
    DatasetNotFoundError,
    DatasetRequestRefused,
    DatasetSnapshotInfo,
    DatasetSpec,
    IDatasetPort,
    QueryResult,
    RowStream,
    WriteMode,
)
from naas_abi_core.services.dataset.iam_catalog import (
    CATALOG,
    CATALOG_TYPE,
    DATASET,
    NAMESPACE,
)
from naas_abi_core.services.dataset.ontologies.classes.ontology_naas_ai.abi.dataset.DatasetCatalogPressure import (
    DatasetCatalogPressure,
)
from naas_abi_core.services.dataset.sql_references import referenced_datasets
from naas_abi_core.services.iam.enforcement import ResourceGuard
from naas_abi_core.services.ServiceBase import ServiceBase


def _deadline(timeout_seconds: float | None) -> dict[str, float]:
    """A caller's deadline, passed on only when given: an adapter written
    before the keyword keeps working for every call without one."""
    return {} if timeout_seconds is None else {"timeout_seconds": timeout_seconds}


class DatasetService(ServiceBase, IDatasetPort):
    """Named tables with a partition spec, queried with SQL.

    The adapter owns bytes and snapshots. This service is a thin facade so
    modules depend on one type (`DatasetService`) like object storage.

    Wired into an engine, every operation is authorized on
    ``dataset/<namespace>/<name>`` (RFC §6.4): a dataset the caller may not
    see is ``DatasetNotFoundError``, a query needs ``Query`` on every dataset
    its SQL reads, and ``list`` returns only what the caller may list.
    """

    __adapter: IDatasetPort

    def __init__(self, adapter: IDatasetPort):
        super().__init__()
        self.__adapter = adapter
        self._guard = ResourceGuard.of(CATALOG, self)

    def __dataset(self, action: str, name: str, namespace: str) -> None:
        self._guard.require(
            action,
            DATASET,
            [namespace, name],
            not_found=lambda: DatasetNotFoundError(name, namespace),
        )

    def __query(self, action: str, sql: str, namespace: str) -> None:
        """``action`` on every dataset ``sql`` reads; the first denial fails.

        The SQL must be a single ``SELECT`` over datasets
        (``sql_references``), and every name it reads a dataset of the
        catalog: anything else DuckDB could resolve (a view of its own, the
        lake's metadata) is ``DatasetNotFoundError``, as a dataset the caller
        may not see is. That holds for a caller allowed every dataset too: a
        file-reading function reads no dataset. Only ``QueryUnchecked`` on the
        catalog (the engine's own maintenance) skips it.
        """
        if self._guard.iam is None or self._guard.allowed(
            "QueryUnchecked", CATALOG_TYPE
        ):
            return
        every = self._guard.allows_every(action, DATASET)
        for referenced_namespace, name in referenced_datasets(sql, namespace):
            stored = self.__stored(name, referenced_namespace)
            if stored is None:
                raise DatasetNotFoundError(name, referenced_namespace)
            if not every:
                self.__dataset(action, stored.name, stored.namespace)

    def __stored(self, name: str, namespace: str) -> DatasetInfo | None:
        """The catalog's dataset DuckDB reads for ``namespace.name``. DuckDB
        matches names without case; this looks the dataset up by itself, as
        spelled and in lower case, never by listing the catalog. A dataset
        stored in another case (``Orders`` read as ``orders``) is not found,
        which refuses, never widens."""
        spellings = dict.fromkeys(
            (ns, n)
            for ns in (namespace, namespace.lower())
            for n in (name, name.lower())
        )
        for spelled_namespace, spelled_name in spellings:
            try:
                return self.__adapter.describe(
                    spelled_name, namespace=spelled_namespace
                )
            except DatasetNotFoundError:
                continue
        return None

    @property
    def adapter(self) -> IDatasetPort:
        """The wrapped secondary adapter -- public so callers (e.g.
        ``EngineNATSLoader``) can check what kind of adapter this service is
        backed by, mirroring ``ObjectStorageService.adapter``."""
        return self.__adapter

    def create(self, spec: DatasetSpec) -> DatasetInfo:
        """A create (RFC §4.4): a new namespace is placed in the call's target
        workspace, or on the platform."""
        commit = self._guard.create(
            "Create",
            DATASET,
            [spec.namespace, spec.name],
            container=(NAMESPACE, [spec.namespace]),
            exists=lambda: self.__exists(spec.name, spec.namespace),
            container_exists=lambda: bool(
                self.__adapter.list(namespace=spec.namespace)
            ),
            not_found=lambda: DatasetNotFoundError(spec.name, spec.namespace),
        )
        info = self.__adapter.create(spec)
        commit()
        return info

    def __exists(self, name: str, namespace: str) -> bool:
        try:
            self.__adapter.describe(name, namespace=namespace)
        except DatasetNotFoundError:
            return False
        return True

    def describe(self, name: str, *, namespace: str = "default") -> DatasetInfo:
        self.__dataset("Describe", name, namespace)
        return self.__adapter.describe(name, namespace=namespace)

    def list(self, *, namespace: str | None = None) -> list[DatasetInfo]:
        """The datasets the caller may list (RFC §5.5); never fails for that."""
        return self._guard.filter(
            "List",
            DATASET,
            self.__adapter.list(namespace=namespace),
            lambda info: [info.namespace, info.name],
        )

    def write(
        self,
        name: str,
        rows: builtins.list[dict[str, Any]],
        *,
        namespace: str = "default",
        mode: WriteMode = "append",
        snapshot_id: int | None = None,
    ) -> DatasetInfo:
        self.__dataset("Write", name, namespace)
        return self.__adapter.write(
            name,
            rows,
            namespace=namespace,
            mode=mode,
            snapshot_id=snapshot_id,
        )

    def write_stream(
        self,
        name: str,
        rows: Iterable[dict[str, Any]],
        *,
        namespace: str = "default",
        mode: WriteMode = "append",
        snapshot_id: int | None = None,
    ) -> DatasetInfo:
        self.__dataset("WriteStream", name, namespace)
        return self.__adapter.write_stream(
            name,
            rows,
            namespace=namespace,
            mode=mode,
            snapshot_id=snapshot_id,
        )

    def query(
        self,
        sql: str,
        *,
        namespace: str = "default",
        snapshot_id: int | None = None,
        timeout_seconds: float | None = None,
    ) -> QueryResult:
        self.__query("Query", sql, namespace)
        return self.__adapter.query(
            sql,
            namespace=namespace,
            snapshot_id=snapshot_id,
            **_deadline(timeout_seconds),
        )

    @contextmanager
    def query_stream(
        self,
        sql: str,
        *,
        namespace: str = "default",
        snapshot_id: int | None = None,
    ) -> Iterator[RowStream]:
        self.__query("QueryStream", sql, namespace)
        with self.__adapter.query_stream(
            sql, namespace=namespace, snapshot_id=snapshot_id
        ) as result:
            yield result

    def compact(
        self,
        name: str,
        *,
        namespace: str = "default",
        timeout_seconds: float | None = None,
    ) -> QueryResult:
        self.__dataset("Compact", name, namespace)
        return self.__adapter.compact(
            name, namespace=namespace, **_deadline(timeout_seconds)
        )

    def flush(
        self,
        name: str,
        *,
        namespace: str = "default",
        timeout_seconds: float | None = None,
    ) -> QueryResult:
        self.__dataset("Flush", name, namespace)
        return self.__adapter.flush(
            name, namespace=namespace, **_deadline(timeout_seconds)
        )

    def inlined_row_count(self, name: str, *, namespace: str = "default") -> int:
        self.__dataset("InlinedRowCount", name, namespace)
        return self.__adapter.inlined_row_count(name, namespace=namespace)

    def check_catalog_pressure(
        self, name: str, *, namespace: str = "default", threshold_records: int = 100_000
    ) -> int:
        """Measure accumulation and emit a warning event on each over-limit check."""
        if threshold_records <= 0:
            raise DatasetRequestRefused("threshold_records must be positive")
        count = self.inlined_row_count(name, namespace=namespace)
        if count >= threshold_records:
            logger.warning(
                "Dataset {}.{} has {} unflushed catalog records (threshold {}); "
                "run dataset flushing and compaction.",
                namespace,
                name,
                count,
                threshold_records,
            )
            if self.services_wired and self.services.events_available():
                try:
                    self.services.events.emit(
                        DatasetCatalogPressure(
                            dataset_name=name,
                            namespace=namespace,
                            inlined_records=count,
                            threshold_records=threshold_records,
                        )
                    )
                except Exception as exc:  # noqa: BLE001 - event publication is fail-open
                    logger.warning(
                        "Dataset catalog pressure event publication failed: {}",
                        type(exc).__name__,
                    )
        return count

    def list_snapshots(self) -> builtins.list[DatasetSnapshotInfo]:
        """The catalog's snapshots; none for a caller who may not list them."""
        if not self._guard.allowed("ListSnapshots", CATALOG_TYPE):
            return []
        return self.__adapter.list_snapshots()

    def namespace_version(self, namespace: str) -> int | None:
        """None, as for an unknown namespace, when the caller may not see it."""
        try:
            self._guard.require(
                "NamespaceVersion",
                NAMESPACE,
                [namespace],
                not_found=lambda: DatasetNotFoundError("", namespace),
            )
        except DatasetNotFoundError:
            return None
        return self.__adapter.namespace_version(namespace)

    def drop(self, name: str, *, namespace: str = "default") -> None:
        self.__dataset("Drop", name, namespace)
        self.__adapter.drop(name, namespace=namespace)
