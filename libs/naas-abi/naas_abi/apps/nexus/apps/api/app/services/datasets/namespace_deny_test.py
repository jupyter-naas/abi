"""A Deny on a dataset namespace hides it on every path: list, describe, preview and
a query sent to it, and a query sent to another namespace whose SQL reads it. A real
IAM (``NexusIam``), a kernel ``DatasetService`` over DuckLake wired to it, the real
routes; queries run in the request's call context."""

from __future__ import annotations

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
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.services.dataset.adapters.secondary.DatasetSecondaryAdapterDuckLake import (
    DatasetSecondaryAdapterDuckLake,
)
from naas_abi_core.services.dataset.DatasetPort import ColumnSpec, DatasetSpec
from naas_abi_core.services.dataset.DatasetService import DatasetService

SALARY = 123456.0


def shared_world(tmp_path):
    """``member`` of ws-1, denied the namespace ``hr``; the deployment shares
    ``timesheets`` and ``hr``. Returns ``(nexus, datasets)``; ``nexus`` is installed
    by the caller."""
    nexus = NexusIam()
    return nexus, DatasetService(
        DatasetSecondaryAdapterDuckLake(
            catalog=f"sqlite:{tmp_path / 'datasets.sqlite'}",
            data_path=str(tmp_path / "warehouse"),
            max_retries=10,
            retry_base_delay_seconds=0.01,
        )
    )


def populate(nexus, datasets) -> None:
    scope = nexus.workspace("org-1", "ws-1")
    nexus.grant("member", "member", scope)
    nexus.deny("member", ["nexus:*"], ["abi:nexus:dataset/hr", "abi:nexus:dataset/hr/*"], scope)
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
def http(tmp_path):
    nexus, datasets = shared_world(tmp_path)
    with nexus.installed():
        populate(nexus, datasets)
        app = FastAPI()

        @app.middleware("http")
        async def identity(request, call_next):  # as RequestIdentityMiddleware does
            with use_call_context(NexusIam.context("member")):
                return await call_next(request)

        app.include_router(datasets_api.router, prefix="/datasets")
        app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(id="member")
        app.dependency_overrides[get_datasets_service] = lambda: DatasetsService(datasets)
        yield TestClient(app)


def _query(http, namespace: str, sql: str):
    return http.post(f"/datasets/{namespace}/query", json={"workspace_id": "ws-1", "sql": sql})


def test_a_namespace_deny_keeps_its_rows_from_a_query_of_another_namespace(http) -> None:
    # The member's own namespace answers, in the member's call: the kernel decides.
    own = _query(http, "timesheets", "SELECT * FROM hours")
    assert own.status_code == 200, own.text
    assert own.json()["rows"] == [{"who": "ann", "hours": 2.5}]
    for sql in (
        "SELECT * FROM hr.pay",
        "SELECT * FROM HR.pay",
        "SELECT * FROM Hr.PAY",
        "SELECT h.who FROM hours h JOIN hr.pay p ON p.who = h.who",
        "WITH x AS (SELECT * FROM hr.pay) SELECT * FROM x",
    ):
        refused = _query(http, "timesheets", sql)
        assert refused.status_code == 403, (sql, refused.text)
        assert str(SALARY) not in refused.text
    assert _query(http, "hr", "SELECT * FROM pay").status_code == 403
    # The namespace in the path, in another case, is the same namespace to the kernel.
    for namespace in ("HR", "Hr"):
        assert _query(http, namespace, "SELECT * FROM pay").status_code == 403


def test_a_namespace_deny_hides_it_from_the_catalog(http) -> None:
    params = {"workspace_id": "ws-1"}
    listed = {d["namespace"] for d in http.get("/datasets/", params=params).json()["datasets"]}
    assert listed == {"timesheets"}
    assert http.get("/datasets/hr/pay", params=params).status_code == 403
    assert http.get("/datasets/hr/pay/preview", params=params).status_code == 403
    assert http.get("/datasets/HR/pay/preview", params=params).status_code == 403
    assert http.get("/datasets/HR/PAY", params=params).status_code == 403
