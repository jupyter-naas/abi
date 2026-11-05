"""Offline checks of the module: no broker, no engine."""

from __future__ import annotations

import asyncio

from naas_abi_apps.common.testing import bound_tool_names, fake_engine, no_core_import
from naas_abi_apps.naas import MODULE_ID, ABIModule
from naas_abi_apps.naas.agents.NaasAgent import NAME


def test_the_module_declares_its_agent_and_ontology() -> None:
    assert ABIModule.module_id == MODULE_ID == "applications.naas"
    assert [agent.name for agent in ABIModule.agents] == [NAME]
    assert {o.source(MODULE_ID) for o in ABIModule.get_ontologies()} == {
        "module/applications.naas/NaasOntology.ttl"
    }


def test_tools_need_the_api_key() -> None:
    with_key = fake_engine({"NAAS_API_KEY": "k"})
    without = fake_engine()

    asyncio.run(ABIModule(with_key, ABIModule.Configuration()).on_initialized())
    asyncio.run(ABIModule(without, ABIModule.Configuration()).on_initialized())

    assert len(bound_tool_names(with_key)) > len(bound_tool_names(without))


def test_the_module_never_imports_abi_core() -> None:
    assert no_core_import("naas_abi_apps.naas", "naas_abi_apps.naas.__main__") is None
