"""Datasets FastAPI primary adapter (read-only catalog + SQL)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.datasets.adapters.primary.datasets__primary_adapter__dependencies import (  # noqa: E501
    get_datasets_service,
)
from naas_abi.apps.nexus.apps.api.app.services.datasets.adapters.primary.datasets__primary_adapter__schemas import (  # noqa: E501
    DatasetColumn,
    DatasetInfo,
    DatasetListResponse,
    DatasetPartition,
    DatasetQueryRequest,
    DatasetQueryResponse,
)
from naas_abi.apps.nexus.apps.api.app.services.datasets.datasets__schema import (
    DatasetInfoData,
    DatasetQueryError,
    DatasetQueryResultData,
    DatasetQueryTimeoutError,
    DatasetServiceUnavailableError,
    InvalidDatasetIdentifierError,
)
from naas_abi.apps.nexus.apps.api.app.services.datasets.service import DatasetsService
from naas_abi.apps.nexus.apps.api.app.services.iam import authz
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import declares, guard
from naas_abi_core.services.dataset.DatasetPort import (
    DatasetNotFoundError,
    DatasetSnapshotNotFoundError,
)

router = APIRouter(dependencies=[Depends(get_current_user_required)])


class DatasetsFastAPIPrimaryAdapter:
    def __init__(self) -> None:
        self.router = router


def _to_info(value: DatasetInfoData) -> DatasetInfo:
    return DatasetInfo(
        name=value.name,
        namespace=value.namespace,
        columns=[DatasetColumn(name=col.name, type=col.type) for col in value.columns],
        partitions=[
            DatasetPartition(column=part.column, transform=part.transform)
            for part in value.partitions
        ],
        primary_key=list(value.primary_key),
        snapshot_id=value.snapshot_id,
        location=value.location,
    )


def _to_query(value: DatasetQueryResultData) -> DatasetQueryResponse:
    return DatasetQueryResponse(
        columns=value.columns,
        rows=value.rows,
        truncated=value.truncated,
        limit=value.limit,
    )


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, DatasetServiceUnavailableError):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    if isinstance(exc, DatasetNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, DatasetSnapshotNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, (DatasetQueryError, InvalidDatasetIdentifierError)):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, DatasetQueryTimeoutError):
        return HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get(
    "/",
    response_model=DatasetListResponse,
    dependencies=[guard("ListDatasets", literal="-")],
)
async def list_datasets(
    workspace_id: str = Query(..., min_length=1, max_length=100),
    namespace: str | None = Query(default=None, max_length=128),
    datasets_service: DatasetsService = Depends(get_datasets_service),
):
    try:
        items = datasets_service.list(namespace=namespace)
    except Exception as exc:
        raise _http_error(exc) from exc
    return DatasetListResponse(datasets=[_to_info(item) for item in items], total=len(items))


@router.get(
    "/{namespace}/{name}",
    response_model=DatasetInfo,
    dependencies=[guard("GetDataset", id=("namespace", "name"))],
)
async def describe_dataset(
    namespace: str,
    name: str,
    workspace_id: str = Query(..., min_length=1, max_length=100),
    datasets_service: DatasetsService = Depends(get_datasets_service),
):
    try:
        return _to_info(datasets_service.describe(name, namespace=namespace))
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get(
    "/{namespace}/{name}/preview",
    response_model=DatasetQueryResponse,
    dependencies=[guard("PreviewDataset", id=("namespace", "name"))],
)
async def preview_dataset(
    namespace: str,
    name: str,
    workspace_id: str = Query(..., min_length=1, max_length=100),
    limit: int | None = Query(default=None, ge=1, le=1000),
    snapshot_id: int | None = Query(default=None, ge=0),
    datasets_service: DatasetsService = Depends(get_datasets_service),
):
    try:
        return _to_query(
            datasets_service.preview(
                name,
                namespace=namespace,
                limit=limit,
                snapshot_id=snapshot_id,
            )
        )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post(
    "/{namespace}/query",
    response_model=DatasetQueryResponse,
    dependencies=[declares("QueryDataset")],
)
async def query_namespace(
    namespace: str,
    payload: DatasetQueryRequest,
    current_user: User = Depends(get_current_user_required),
    datasets_service: DatasetsService = Depends(get_datasets_service),
):
    # The workspace is in the body, so the check happens here, not in a guard.
    await authz.require(
        "QueryDataset", user=current_user, workspace=payload.workspace_id, id=namespace
    )
    try:
        return _to_query(
            datasets_service.query(
                payload.sql,
                namespace=namespace,
                limit=payload.limit,
                snapshot_id=payload.snapshot_id,
            )
        )
    except Exception as exc:
        raise _http_error(exc) from exc
