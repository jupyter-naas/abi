from __future__ import annotations

# ``list`` is a port method name, so it shadows the builtin for annotations
# evaluated in the class bodies below; use ``builtins.list`` there.
import builtins
from typing import Any

from naas_abi_core import logger
from naas_abi_core.services.dataset.DatasetPort import (
    DatasetInfo,
    DatasetSnapshotInfo,
    DatasetSpec,
    IDatasetPort,
    QueryResult,
    WriteMode,
)
from naas_abi_core.services.dataset.ontologies.classes.ontology_naas_ai.abi.dataset.DatasetCatalogPressure import (
    DatasetCatalogPressure,
)
from naas_abi_core.services.ServiceBase import ServiceBase


class DatasetService(ServiceBase, IDatasetPort):
    """Named tables with a partition spec, queried with SQL.

    The adapter owns bytes and snapshots. This service is a thin facade so
    modules depend on one type (`DatasetService`) like object storage.
    """

    __adapter: IDatasetPort

    def __init__(self, adapter: IDatasetPort):
        super().__init__()
        self.__adapter = adapter

    def create(self, spec: DatasetSpec) -> DatasetInfo:
        return self.__adapter.create(spec)

    def describe(self, name: str, *, namespace: str = "default") -> DatasetInfo:
        return self.__adapter.describe(name, namespace=namespace)

    def list(self, *, namespace: str | None = None) -> list[DatasetInfo]:
        return self.__adapter.list(namespace=namespace)

    def write(
        self,
        name: str,
        rows: builtins.list[dict[str, Any]],
        *,
        namespace: str = "default",
        mode: WriteMode = "append",
        snapshot_id: int | None = None,
    ) -> DatasetInfo:
        return self.__adapter.write(
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
    ) -> QueryResult:
        return self.__adapter.query(sql, namespace=namespace, snapshot_id=snapshot_id)

    def compact(self, name: str, *, namespace: str = "default") -> QueryResult:
        return self.__adapter.compact(name, namespace=namespace)

    def flush(self, name: str, *, namespace: str = "default") -> QueryResult:
        return self.__adapter.flush(name, namespace=namespace)

    def inlined_row_count(self, name: str, *, namespace: str = "default") -> int:
        return self.__adapter.inlined_row_count(name, namespace=namespace)

    def check_catalog_pressure(
        self, name: str, *, namespace: str = "default", threshold_records: int = 100_000
    ) -> int:
        """Measure accumulation and emit a warning event on each over-limit check."""
        if threshold_records <= 0:
            raise ValueError("threshold_records must be positive")
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
                    self.services.events.publish(
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
        return self.__adapter.list_snapshots()

    def drop(self, name: str, *, namespace: str = "default") -> None:
        self.__adapter.drop(name, namespace=namespace)
