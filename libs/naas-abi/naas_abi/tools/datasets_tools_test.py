"""The Datasets agent's tools and the Sheets agent's dataset connector decide as the
dataset routes do: a Deny on a namespace keeps it out of their listing, their
describe, preview and query, and their import, whatever namespace the call names.
Real IAM, a kernel ``DatasetService`` wired to it, the turn's call context."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest
from naas_abi_core.engine.call_context import use_call_context

import naas_abi
from naas_abi.apps.nexus.apps.api.app.services.datasets.namespace_deny_test import (
    SALARY,
    populate,
    shared_world,
)
from naas_abi.apps.nexus.apps.api.app.services.datasets.service import DatasetsService
from naas_abi.apps.nexus.apps.api.app.services.iam.names import workspace_container
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.sheets.model import SheetWorkbook
from naas_abi.tools import datasets_tools, sheets_tools


@pytest.fixture
def turn(tmp_path, monkeypatch):
    nexus, datasets = shared_world(tmp_path)
    with nexus.installed():
        populate(nexus, datasets)
        monkeypatch.setattr(
            datasets_tools, "_service", lambda: DatasetsService(datasets)
        )
        # Membership is the workspace service's; what is decided here is IAM's.
        monkeypatch.setattr(
            datasets_tools, "check_member", lambda user_id, ws: "member"
        )
        engine = SimpleNamespace(
            services=SimpleNamespace(dataset_available=lambda: True, dataset=datasets)
        )
        monkeypatch.setattr(
            naas_abi.ABIModule,
            "get_instance",
            staticmethod(lambda: SimpleNamespace(engine=engine)),
        )
        written: list = []
        monkeypatch.setattr(sheets_tools.store, "resolve_slug", lambda slug: "workbook")
        monkeypatch.setattr(
            sheets_tools,
            "_load_model",
            lambda slug: (SheetWorkbook(sheets=[]), "", "stub"),
        )

        def persist(slug, workbook, html, message):
            written.extend(row for tab in workbook.sheets for row in tab.rows)
            return {"slug": slug}

        monkeypatch.setattr(sheets_tools, "_persist_model", persist)
        context = replace(
            NexusIam.context("member"), container=workspace_container("org-1", "ws-1")
        )
        with use_call_context(context):
            yield SimpleNamespace(
                datasets={t.name: t for t in datasets_tools.datasets_tools()},
                sheets={t.name: t for t in sheets_tools.sheets_tools()},
                written=written,
            )


def test_the_datasets_agent_keeps_a_namespace_deny(turn) -> None:
    tools = turn.datasets
    listed = tools["list_datasets"].invoke({})
    assert [row["dataset"] for row in listed["datasets"]] == ["timesheets/hours"]
    for name in ("describe_dataset", "preview_dataset"):
        refused = tools[name].invoke({"dataset": "hr/pay"})
        assert "error" in refused and str(SALARY) not in str(refused)
    own = tools["query_datasets"].invoke(
        {"sql": "SELECT * FROM hours", "namespace": "timesheets"}
    )
    assert own["rows"] == [{"who": "ann", "hours": 2.5}]
    for namespace, sql in (
        ("timesheets", "SELECT * FROM hr.pay"),
        ("hr", "SELECT * FROM pay"),
    ):
        refused = tools["query_datasets"].invoke({"sql": sql, "namespace": namespace})
        assert "error" in refused and str(SALARY) not in str(refused)


def test_the_sheets_connector_keeps_a_namespace_deny(turn) -> None:
    importing = turn.sheets["import_dataset_to_sheet"]
    refused = importing.invoke({"dataset_name": "pay", "namespace": "hr"})
    assert "error" in refused and turn.written == []
    odd = importing.invoke({"dataset_name": 'pay" --', "namespace": "hr"})
    assert "error" in odd and turn.written == []
    made = importing.invoke({"dataset_name": "hours", "namespace": "timesheets"})
    assert made.get("ok") is True
    assert turn.written == [["who", "hours"], ["ann", 2.5]]
