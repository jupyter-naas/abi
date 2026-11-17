"""Workspace roles read the kernel dataset namespaces the deployment shares, and no
other: never the engine's event archive, nor what a kernel job writes. A real IAM
(``NexusIam``), a kernel ``DatasetService`` over DuckLake wired to it, the real
archive job and the real dataset routes."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import get_current_user_required
from naas_abi.apps.nexus.apps.api.app.services.datasets.adapters.primary import (
    datasets__primary_adapter__FastAPI as datasets_api,
)
from naas_abi.apps.nexus.apps.api.app.services.datasets.adapters.primary.datasets__primary_adapter__dependencies import (  # noqa: E501
    get_datasets_service,
)
from naas_abi.apps.nexus.apps.api.app.services.datasets.service import DatasetsService
from naas_abi.apps.nexus.apps.api.app.services.iam.bootstrap import shared_repo_grants
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi_core.engine.call_context import as_service_account, use_call_context
from naas_abi_core.engine.engine_loaders.EngineJobLoader import job_identity
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.services.dataset.adapters.secondary.DatasetSecondaryAdapterDuckLake import (
    DatasetSecondaryAdapterDuckLake,
)
from naas_abi_core.services.dataset.DatasetPort import ColumnSpec, DatasetSpec
from naas_abi_core.services.dataset.DatasetService import DatasetService
from naas_abi_core.services.event.adapters.secondary.EventPostgreSQLAdapter import (
    ArchiveBoundary,
)
from naas_abi_core.services.event.adapters.secondary.EventPostgreSQLArchive import (
    ARCHIVE_DATASET,
    EVENT_ARCHIVE_OWNER,
    EventArchiveJobs,
)
from naas_abi_core.services.event.EventPort import StoredEvent

ARCHIVE = "abi_event"  # the PostgreSQL event adapter's default schema
SHARED = "shared_reference"
CHAT = "a chat message of another organization"


class _OldEvents:
    """The part of the PostgreSQL event log the archive job reads: one old event."""

    def __init__(self) -> None:
        self.events = [
            StoredEvent(
                id="urn:event:1",
                event_type="urn:class:AgentUserMessageReceived",
                seq=1,
                timestamp="2026-01-01T00:00:00+00:00",
                payload=CHAT.encode(),
            )
        ]

    def query(self, *, since_seq: int = 0, until_seq: int | None = None, limit: int = 100):
        return [
            e
            for e in self.events
            if e.seq > since_seq and (until_seq is None or e.seq <= until_seq)
        ][:limit]

    def archivable_through(self, cutoff, consumers_active_since=None):
        return ArchiveBoundary(max((e.seq for e in self.events), default=0))

    def remove_through(self, seq: int) -> int:
        return 0


@pytest.fixture
def world(tmp_path):
    nexus = NexusIam()
    with nexus.installed():
        ws_a = nexus.workspace("org-A", "ws-A")
        nexus.workspace("org-B", "ws-B")
        nexus.grant("viewer", "viewer", ws_a)
        nexus.grant("member", "member", ws_a)
        with as_service_account("engine"):
            nexus.iam.set_platform_grants(shared_repo_grants("abi/monorepo", [SHARED]))
        datasets = DatasetService(
            DatasetSecondaryAdapterDuckLake(
                catalog=f"sqlite:{tmp_path / 'datasets.sqlite'}",
                data_path=str(tmp_path / "warehouse"),
                max_retries=10,
                retry_base_delay_seconds=0.01,
            )
        )
        datasets.set_services(IEngine.Services(iam=nexus.iam))
        # The archive job, as the engine hosts it: its own account, no user, no container.
        account = job_identity(nexus.iam, EVENT_ARCHIVE_OWNER)
        with as_service_account(account):
            report = EventArchiveJobs(
                _OldEvents(), datasets, namespace=ARCHIVE, retain=timedelta(days=7)
            ).run(now=datetime.now(UTC))
        assert report.archived == 1
        # A dataset the deployment shares, and one another kernel job writes.
        spec = (ColumnSpec(name="v", type="string"),)
        with as_service_account("engine"):
            datasets.create(DatasetSpec(name="codes", namespace=SHARED, columns=spec))
        with as_service_account(job_identity(nexus.iam, "naas_abi_core.some_job")):
            datasets.create(DatasetSpec(name="state", namespace="kernel_job", columns=spec))
        yield SimpleNamespace(nexus=nexus, datasets=datasets, workspace=ws_a)


def _routes(world, user: str) -> TestClient:
    context = replace(NexusIam.context(user), container=world.workspace)
    app = FastAPI()

    @app.middleware("http")
    async def identity(request, call_next):  # as RequestIdentityMiddleware does
        with use_call_context(context):
            return await call_next(request)

    app.include_router(datasets_api.router, prefix="/datasets")
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(id=user)
    app.dependency_overrides[get_datasets_service] = lambda: DatasetsService(world.datasets)
    return TestClient(app)


@pytest.mark.parametrize("user", ["viewer", "member"])
def test_the_event_archive_stays_the_engines(world, user) -> None:
    http = _routes(world, user)
    listed = http.get("/datasets/", params={"workspace_id": "ws-A"})
    assert listed.status_code == 200
    names = {d["namespace"] for d in listed.json()["datasets"]}
    assert ARCHIVE not in names
    described = http.get(f"/datasets/{ARCHIVE}/{ARCHIVE_DATASET}", params={"workspace_id": "ws-A"})
    assert described.status_code == 404
    # What the agents' tools do: the kernel query, in the user's own call.
    with use_call_context(replace(NexusIam.context(user), container=world.workspace)):
        with pytest.raises(Exception) as refused:
            world.datasets.query(f"SELECT payload FROM {ARCHIVE_DATASET}", namespace=ARCHIVE)
    assert CHAT not in str(refused.value)


@pytest.mark.parametrize("user", ["viewer", "member"])
def test_a_workspace_role_reaches_no_namespace_a_kernel_job_created(world, user) -> None:
    with use_call_context(replace(NexusIam.context(user), container=world.workspace)):
        reachable = {d.namespace for d in world.datasets.list()}
    # The namespace the deployment shares, and none of the kernel jobs'.
    assert reachable == {SHARED}
