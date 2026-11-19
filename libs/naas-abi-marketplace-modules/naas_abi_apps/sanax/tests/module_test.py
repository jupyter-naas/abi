"""Offline checks of the module: no broker, no engine."""

from __future__ import annotations

import asyncio

from naas_abi_apps.common.testing import (
    FakeTripleStore,
    bound_tool_names,
    fake_engine,
    no_core_import,
)
from naas_abi_apps.sanax import MODULE_ID, ABIModule
from naas_abi_apps.sanax.agents.SanaxAgent import NAME


def test_the_module_declares_its_agent_pipeline_and_ontologies() -> None:
    assert ABIModule.module_id == MODULE_ID == "applications.sanax"
    assert [agent.name for agent in ABIModule.agents] == [NAME]
    assert set(ABIModule.get_pipeline_classes()) == {
        "sanax_linked_in_sales_navigator_extractor_pipeline"
    }
    assert {o.source(MODULE_ID) for o in ABIModule.get_ontologies()} == {
        "module/applications.sanax/SanaxLinkedInSalesNavigatorSparqlQueries.ttl"
    }


def test_on_initialized_binds_count_items_and_the_fourteen_templates() -> None:
    engine = fake_engine()
    engine.services.triple_store = FakeTripleStore()
    module = ABIModule(engine, ABIModule.Configuration())

    asyncio.run(module.on_initialized())

    names = bound_tool_names(engine)
    assert set(module._agent_handlers) == {NAME}
    assert "count_items" in names
    assert len([n for n in names if n.startswith("sanax_")]) == 14


def test_the_module_never_imports_abi_core() -> None:
    assert no_core_import("naas_abi_apps.sanax", "naas_abi_apps.sanax.__main__") is None
