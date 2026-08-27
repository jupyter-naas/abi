from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.datasets.datasets__schema import (
    DatasetColumnData,
    DatasetInfoData,
    DatasetPartitionData,
    DatasetQueryResultData,
    DatasetQueryTimeoutError,
    DatasetServiceUnavailableError,
    InvalidDatasetIdentifierError,
)
from naas_abi.apps.nexus.apps.api.app.services.datasets.sql_safe import (
    DEFAULT_PREVIEW_LIMIT,
    DEFAULT_QUERY_LIMIT,
    MAX_PREVIEW_LIMIT,
    MAX_QUERY_LIMIT,
    assert_read_only_sql,
    clamp_limit,
    preview_sql,
    wrap_limit,
)
from naas_abi_core.services.dataset.DatasetPort import IDENTIFIER_PATTERN, DatasetInfo
from naas_abi_core.services.dataset.DatasetService import DatasetService

_IDENTIFIER = re.compile(IDENTIFIER_PATTERN)
_QUERY_TIMEOUT_SECONDS = 15.0
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="nexus-datasets")


class DatasetsService:
    """Read-only catalog + SQL over engine DatasetService."""

    def __init__(self, dataset: DatasetService | None):
        self._dataset = dataset

    def list(self, *, namespace: str | None = None) -> list[DatasetInfoData]:
        dataset = self._require_dataset()
        if namespace is not None:
            self._require_identifier("namespace", namespace)
        return [self._to_info(item) for item in dataset.list(namespace=namespace)]

    def describe(self, name: str, *, namespace: str) -> DatasetInfoData:
        dataset = self._require_dataset()
        self._require_identifier("name", name)
        self._require_identifier("namespace", namespace)
        return self._to_info(dataset.describe(name, namespace=namespace))

    def preview(
        self,
        name: str,
        *,
        namespace: str,
        limit: int | None = None,
        snapshot_id: str | None = None,
    ) -> DatasetQueryResultData:
        self.describe(name, namespace=namespace)
        capped = clamp_limit(
            limit, default=DEFAULT_PREVIEW_LIMIT, maximum=MAX_PREVIEW_LIMIT
        )
        return self._execute(
            preview_sql(name, capped),
            namespace=namespace,
            snapshot_id=snapshot_id,
            limit=capped,
            wrap=False,
        )

    def query(
        self,
        sql: str,
        *,
        namespace: str,
        limit: int | None = None,
        snapshot_id: str | None = None,
    ) -> DatasetQueryResultData:
        self._require_dataset()
        self._require_identifier("namespace", namespace)
        cleaned = assert_read_only_sql(sql)
        capped = clamp_limit(
            limit, default=DEFAULT_QUERY_LIMIT, maximum=MAX_QUERY_LIMIT
        )
        return self._execute(
            cleaned,
            namespace=namespace,
            snapshot_id=snapshot_id,
            limit=capped,
            wrap=True,
        )

    def _execute(
        self,
        sql: str,
        *,
        namespace: str,
        snapshot_id: str | None,
        limit: int,
        wrap: bool,
    ) -> DatasetQueryResultData:
        dataset = self._require_dataset()
        statement = wrap_limit(sql, limit) if wrap else sql
        future = _executor.submit(
            dataset.query,
            statement,
            namespace=namespace,
            snapshot_id=snapshot_id,
        )
        try:
            result = future.result(timeout=_QUERY_TIMEOUT_SECONDS)
        except FuturesTimeout as exc:
            raise DatasetQueryTimeoutError(_QUERY_TIMEOUT_SECONDS) from exc
        rows = [_jsonable_row(row) for row in result.rows]
        truncated = wrap and len(rows) >= limit
        return DatasetQueryResultData(
            columns=list(result.columns),
            rows=rows,
            truncated=truncated,
            limit=limit,
        )

    def _require_dataset(self) -> DatasetService:
        if self._dataset is None:
            raise DatasetServiceUnavailableError()
        return self._dataset

    @staticmethod
    def _require_identifier(label: str, value: str) -> str:
        text = str(value).strip()
        if not _IDENTIFIER.fullmatch(text):
            raise InvalidDatasetIdentifierError(label, value)
        return text

    @staticmethod
    def _to_info(info: DatasetInfo) -> DatasetInfoData:
        return DatasetInfoData(
            name=info.name,
            namespace=info.namespace,
            columns=tuple(
                DatasetColumnData(name=col.name, type=col.type) for col in info.columns
            ),
            partitions=tuple(
                DatasetPartitionData(column=part.column, transform=part.transform)
                for part in info.partitions
            ),
            snapshot_id=info.snapshot_id,
            location=info.location,
        )


def _jsonable_row(row: dict[str, Any]) -> dict[str, Any]:
    from decimal import Decimal

    out: dict[str, Any] = {}
    for key, value in row.items():
        if hasattr(value, "isoformat"):
            out[key] = value.isoformat()
        elif isinstance(value, (bytes, bytearray)):
            out[key] = value.decode("utf-8", errors="replace")
        elif isinstance(value, Decimal):
            out[key] = float(value)
        elif isinstance(value, (int, float, str, bool)) or value is None:
            out[key] = value
        else:
            out[key] = str(value)
    return out
