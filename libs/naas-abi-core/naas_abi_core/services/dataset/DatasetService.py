from __future__ import annotations

from typing import Any

from naas_abi_core.services.dataset.DatasetPort import (
    DatasetInfo,
    DatasetSpec,
    IDatasetPort,
    QueryResult,
    WriteMode,
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
        rows: list[dict[str, Any]],
        *,
        namespace: str = "default",
        mode: WriteMode = "append",
        snapshot_id: str | None = None,
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
        snapshot_id: str | None = None,
    ) -> QueryResult:
        return self.__adapter.query(
            sql, namespace=namespace, snapshot_id=snapshot_id
        )

    def drop(self, name: str, *, namespace: str = "default") -> None:
        self.__adapter.drop(name, namespace=namespace)
