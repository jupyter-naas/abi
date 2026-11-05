"""Offline checks of the module: no broker, no engine."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from naas_abi_apps.common.testing import MemoryStorage, no_core_import
from naas_abi_apps.sec_gov import MODULE_ID, ABIModule


def test_the_module_publishes_its_workflows_and_no_agent() -> None:
    assert ABIModule.module_id == MODULE_ID == "applications.sec_gov"
    assert ABIModule.agents == ()
    assert set(ABIModule.dependencies.services) == {"document", "object_storage"}
    assert set(ABIModule.get_workflow_classes()) == {
        "download_company_tickers_workflow",
        "get_company_submissions_workflow",
    }


def test_the_workflows_are_built_from_the_module() -> None:
    storage = MemoryStorage()
    engine = SimpleNamespace(services=SimpleNamespace(object_storage=storage))
    module = ABIModule(engine, ABIModule.Configuration(user_agent="ACME (ops@acme.io)"))

    asyncio.run(module.build_processes())

    workflow = module.get_workflow_instance("get_company_submissions_workflow")
    assert workflow.integration_configuration.user_agent == "ACME (ops@acme.io)"
    assert workflow.integration_configuration.storage is storage


def test_the_module_never_imports_abi_core() -> None:
    assert (
        no_core_import(
            "naas_abi_apps.sec_gov",
            "naas_abi_apps.sec_gov.__main__",
            "naas_abi_apps.sec_gov.workflows.DownloadCompanyTickersWorkflow",
            "naas_abi_apps.sec_gov.workflows.GetCompanySubmissionsWorkflow",
        )
        is None
    )
