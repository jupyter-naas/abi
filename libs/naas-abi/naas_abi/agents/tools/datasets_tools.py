"""DatasetsAgent tools for Nexus Datasets (read-only catalog + SQL).

Same operations as ``/api/datasets`` (list, describe, preview, namespace
query) with the same membership check. SQL goes through
``DatasetsService.query``, which enforces read-only statements
(``sql_safe.assert_read_only_sql``) and caps the row limit, so the agent has
no more power than the Datasets page. The dataset open on
``/datasets/<namespace>/<name>`` arrives as the open feature resource (kind
``dataset``, id ``namespace/name``).
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool, tool
from naas_abi.agents.feature.context import active_feature_resource_id
from naas_abi.agents.feature.runtime import (
    check_member,
    guarded,
    jsonable,
    matches,
    tool_context,
)

DATASET_RESOURCE_KIND = "dataset"
_FEATURE = "Datasets"
_MAX_ROWS = 50


def _service() -> Any:
    from naas_abi import ABIModule
    from naas_abi.apps.nexus.apps.api.app.services.datasets.service import (
        DatasetsService,
    )

    services = ABIModule.get_instance().engine.services
    return DatasetsService(services.dataset if services.dataset_available() else None)


def _split(dataset: str) -> tuple[str, str] | dict[str, str]:
    wanted = (dataset or "").strip() or active_feature_resource_id(
        DATASET_RESOURCE_KIND
    )
    if not wanted:
        return {
            "error": "No dataset is open. Pass dataset as namespace/name (see list_datasets)."
        }
    namespace, sep, name = wanted.partition("/")
    if not sep or not namespace or not name:
        return {"error": f"dataset must be namespace/name, got: {wanted}"}
    return namespace, name


def _known_error(exc: Exception) -> dict[str, str] | None:
    from naas_abi.apps.nexus.apps.api.app.services.datasets.datasets__schema import (
        DatasetQueryError,
        DatasetQueryTimeoutError,
        DatasetServiceUnavailableError,
        InvalidDatasetIdentifierError,
    )
    from naas_abi_core.services.dataset.DatasetPort import (
        DatasetNotFoundError,
        DatasetSnapshotNotFoundError,
    )

    known = (
        DatasetQueryError,
        DatasetQueryTimeoutError,
        DatasetServiceUnavailableError,
        InvalidDatasetIdentifierError,
        DatasetNotFoundError,
        DatasetSnapshotNotFoundError,
    )
    if isinstance(exc, known):
        return {"error": f"{type(exc).__name__}: {exc}"}
    return None


def _call(user_id: str, workspace_id: str, fn: Any) -> Any:
    def _run() -> Any:
        role = check_member(user_id, workspace_id)
        if isinstance(role, dict):
            return role
        try:
            return fn()
        except Exception as exc:
            known = _known_error(exc)
            if known:
                return known
            raise

    return guarded(_FEATURE, _run)


def _result(result: Any) -> dict[str, Any]:
    rows = jsonable(result.rows)[:_MAX_ROWS]
    return {
        "columns": result.columns,
        "rows": rows,
        "truncated": bool(result.truncated) or len(result.rows) > _MAX_ROWS,
        "limit": result.limit,
    }


def datasets_tools() -> list[BaseTool]:
    @tool
    def list_datasets(namespace: str = "", query: str = "") -> Any:
        """List datasets (namespace, name, column count, snapshot). Filter by
        namespace or a name query."""
        ctx = tool_context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx
        open_id = active_feature_resource_id(DATASET_RESOURCE_KIND)

        def _list() -> Any:
            items = _service().list(namespace=(namespace or "").strip() or None)
            rows = [
                {
                    "dataset": f"{i.namespace}/{i.name}",
                    "columns": len(i.columns),
                    "snapshot_id": i.snapshot_id,
                }
                for i in items
                if matches(query, i.name, i.namespace)
            ]
            return {"open_dataset": open_id, "total": len(rows), "datasets": rows[:100]}

        return _call(user_id, workspace_id, _list)

    @tool
    def describe_dataset(dataset: str = "") -> Any:
        """Schema of a dataset: columns and types, partitions, primary key,
        snapshot, location. dataset is namespace/name; omit to use the open one."""
        ctx = tool_context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx
        parts = _split(dataset)
        if isinstance(parts, dict):
            return parts
        namespace, name = parts
        return _call(
            user_id,
            workspace_id,
            lambda: jsonable(_service().describe(name, namespace=namespace)),
        )

    @tool
    def preview_dataset(dataset: str = "", limit: int = 20) -> Any:
        """First rows of a dataset (namespace/name; omit for the open one)."""
        ctx = tool_context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx
        parts = _split(dataset)
        if isinstance(parts, dict):
            return parts
        namespace, name = parts
        return _call(
            user_id,
            workspace_id,
            lambda: _result(_service().preview(name, namespace=namespace, limit=limit)),
        )

    @tool
    def query_datasets(sql: str, namespace: str = "", limit: int = 50) -> Any:
        """Run a read-only SQL SELECT over one namespace's datasets.

        Tables are referenced by dataset name. Writes and DDL are rejected by
        the service. namespace defaults to the open dataset's namespace.
        """
        ctx = tool_context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx
        target = (namespace or "").strip()
        if not target:
            parts = _split("")
            if isinstance(parts, dict):
                return {"error": "Pass namespace (see list_datasets)."}
            target = parts[0]
        return _call(
            user_id,
            workspace_id,
            lambda: _result(_service().query(sql, namespace=target, limit=limit)),
        )

    return [list_datasets, describe_dataset, preview_dataset, query_datasets]
