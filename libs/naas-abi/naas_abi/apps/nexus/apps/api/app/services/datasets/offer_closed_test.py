"""A namespace a workspace closes in its offer ("<W> access" or its organization's "<O>
access", ``OfferDatasetsDeny``) is hidden there on every path, as a namespace Deny is:
list, describe, preview, a query sent to it and a query whose SQL reads it. Another
workspace still reads it. The real routes over a kernel ``DatasetService``; the offers
are given (``access._offers_of``)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import get_current_user_required
from naas_abi.apps.nexus.apps.api.app.services.datasets import access
from naas_abi.apps.nexus.apps.api.app.services.datasets.adapters.primary import (
    datasets__primary_adapter__FastAPI as datasets_api,
)
from naas_abi.apps.nexus.apps.api.app.services.datasets.adapters.primary.datasets__primary_adapter__dependencies import (  # noqa: E501
    get_datasets_service,
)
from naas_abi.apps.nexus.apps.api.app.services.datasets.namespace_deny_test import (
    SALARY,
    shared_world,
)
from naas_abi.apps.nexus.apps.api.app.services.datasets.service import DatasetsService
from naas_abi.apps.nexus.apps.api.app.services.iam.bootstrap import shared_repo_grants
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import Offer
from naas_abi_core.engine.call_context import as_service_account, use_call_context
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.services.dataset.DatasetPort import ColumnSpec, DatasetSpec


def populate(nexus, datasets) -> None:
    """``member`` of ws-1 and ws-2, no Deny of their own; the deployment shares
    ``timesheets`` and ``hr``."""
    for workspace in ("ws-1", "ws-2"):
        nexus.grant("member", "member", nexus.workspace("org-1", workspace))
    with as_service_account("engine"):
        nexus.iam.set_platform_grants(shared_repo_grants("abi/monorepo", ["timesheets", "hr"]))
    datasets.set_services(IEngine.Services(iam=nexus.iam))
    with as_service_account("engine"):
        for namespace, name, column in (("timesheets", "hours", "hours"), ("hr", "pay", "salary")):
            datasets.create(
                DatasetSpec(
                    name=name,
                    namespace=namespace,
                    columns=(
                        ColumnSpec(name="who", type="string"),
                        ColumnSpec(name=column, type="double"),
                    ),
                )
            )
        datasets.write("hours", [{"who": "ann", "hours": 2.5}], namespace="timesheets")
        datasets.write("pay", [{"who": "ann", "salary": SALARY}], namespace="hr")


@pytest.fixture
def http(tmp_path, monkeypatch):
    nexus, datasets = shared_world(tmp_path)

    async def offers_of(workspace_id: str):
        # ws-1 closes ``hr`` (its organization closes nothing); ws-2 closes nothing.
        if workspace_id == "ws-1":
            return [Offer.of(features=["datasets"], datasets_closed=["hr"]), None]
        return [Offer.of(features=["datasets"])]

    monkeypatch.setattr(access, "_offers_of", offers_of)
    with nexus.installed():
        populate(nexus, datasets)
        app = FastAPI()

        @app.middleware("http")
        async def identity(request, call_next):
            with use_call_context(NexusIam.context("member")):
                return await call_next(request)

        app.include_router(datasets_api.router, prefix="/datasets")
        app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(id="member")
        app.dependency_overrides[get_datasets_service] = lambda: DatasetsService(datasets)
        yield TestClient(app)


def _query(http, workspace: str, namespace: str, sql: str):
    return http.post(f"/datasets/{namespace}/query", json={"workspace_id": workspace, "sql": sql})


def test_a_closed_namespace_is_hidden_from_the_workspace_catalog(http) -> None:
    listed = http.get("/datasets/", params={"workspace_id": "ws-1"}).json()["datasets"]
    assert {d["namespace"] for d in listed} == {"timesheets"}
    for path in ("/datasets/hr/pay", "/datasets/hr/pay/preview", "/datasets/HR/PAY"):
        refused = http.get(path, params={"workspace_id": "ws-1"})
        assert refused.status_code == 403, (path, refused.text)
        assert "not offered in this workspace" in refused.json()["detail"]


def test_a_closed_namespace_answers_no_query_even_through_another(http) -> None:
    assert _query(http, "ws-1", "timesheets", "SELECT * FROM hours").status_code == 200
    for namespace, sql in (("hr", "SELECT * FROM pay"), ("timesheets", "SELECT * FROM Hr.pay")):
        refused = _query(http, "ws-1", namespace, sql)
        assert refused.status_code == 403, (namespace, sql, refused.text)
        assert str(SALARY) not in refused.text


def test_another_workspace_still_reads_it(http) -> None:
    listed = http.get("/datasets/", params={"workspace_id": "ws-2"}).json()["datasets"]
    assert {d["namespace"] for d in listed} == {"timesheets", "hr"}
    assert _query(http, "ws-2", "hr", "SELECT * FROM pay").status_code == 200


@pytest.mark.asyncio
async def test_the_closed_namespaces_are_the_workspace_s_and_its_organization_s(monkeypatch):
    async def offers_of(_workspace_id: str):
        return [Offer.of(datasets_closed=["HR"]), Offer.of(datasets_closed=["finance"]), None]

    monkeypatch.setattr(access, "_offers_of", offers_of)
    assert await access.closed_namespaces("ws-1") == frozenset({"hr", "finance"})


@pytest.fixture
def http_one_dataset(tmp_path, monkeypatch):
    """ws-1 closes one dataset, ``timesheets/hours``, not its namespace."""
    nexus, datasets = shared_world(tmp_path)

    async def offers_of(workspace_id: str):
        if workspace_id == "ws-1":
            return [Offer.of(features=["datasets"], datasets_closed=["timesheets/hours"]), None]
        return [Offer.of(features=["datasets"])]

    monkeypatch.setattr(access, "_offers_of", offers_of)
    with nexus.installed():
        populate(nexus, datasets)
        app = FastAPI()

        @app.middleware("http")
        async def identity(request, call_next):
            with use_call_context(NexusIam.context("member")):
                return await call_next(request)

        app.include_router(datasets_api.router, prefix="/datasets")
        app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(id="member")
        app.dependency_overrides[get_datasets_service] = lambda: DatasetsService(datasets)
        yield TestClient(app)


def test_a_closed_dataset_is_hidden_and_refused_its_namespace_kept(http_one_dataset) -> None:
    http = http_one_dataset
    listed = http.get("/datasets/", params={"workspace_id": "ws-1"}).json()["datasets"]
    assert {(d["namespace"], d["name"]) for d in listed} == {("hr", "pay")}
    for path in ("/datasets/timesheets/hours", "/datasets/TimeSheets/HOURS/preview"):
        refused = http.get(path, params={"workspace_id": "ws-1"})
        assert refused.status_code == 403, (path, refused.text)
    for namespace, sql in (
        ("timesheets", "SELECT * FROM hours"),
        ("hr", "SELECT * FROM timesheets.hours"),
    ):
        assert _query(http, "ws-1", namespace, sql).status_code == 403, (namespace, sql)
    assert _query(http, "ws-1", "hr", "SELECT * FROM pay").status_code == 200
    # Another workspace still reads it.
    assert _query(http, "ws-2", "timesheets", "SELECT * FROM hours").status_code == 200


@pytest.mark.asyncio
async def test_the_closures_split_into_namespaces_and_datasets(monkeypatch):
    async def offers_of(_workspace_id: str):
        return [
            Offer.of(datasets_closed=["HR", "Finance/Sales"]),
            Offer.of(datasets_closed=["ops/Runs"]),
            None,
        ]

    monkeypatch.setattr(access, "_offers_of", offers_of)
    closed = await access.closed_datasets("ws-1")
    assert closed.namespaces == frozenset({"hr"})
    assert closed.datasets == frozenset({("finance", "sales"), ("ops", "runs")})
    assert await access.closed_namespaces("ws-1") == frozenset({"hr"})
