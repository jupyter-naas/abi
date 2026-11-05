"""Offline checks of the module: no broker, no engine."""

from __future__ import annotations

import asyncio

from naas_abi_apps.common.testing import bound_tool_names, fake_engine, no_core_import
from naas_abi_apps.pubmed import MODULE_ID, ABIModule
from naas_abi_apps.pubmed.agents.PubMedAgent import NAME


def test_the_module_declares_its_agent_pipeline_and_ontology() -> None:
    assert ABIModule.module_id == MODULE_ID == "applications.pubmed"
    assert [agent.name for agent in ABIModule.agents] == [NAME]
    assert set(ABIModule.get_pipeline_classes()) == {"pub_med_pipeline"}
    assert {o.source(MODULE_ID) for o in ABIModule.get_ontologies()} == {
        "module/applications.pubmed/PubMed.ttl"
    }


def test_on_initialized_binds_the_in_engine_tools() -> None:
    engine = fake_engine()
    module = ABIModule(engine, ABIModule.Configuration())

    asyncio.run(module.on_initialized())

    assert set(module._agent_handlers) == {NAME}
    assert {"search_downloadable_pubmed_papers", "download_pdf"} <= bound_tool_names(
        engine
    )


def test_the_module_never_imports_abi_core() -> None:
    assert (
        no_core_import("naas_abi_apps.pubmed", "naas_abi_apps.pubmed.__main__") is None
    )
