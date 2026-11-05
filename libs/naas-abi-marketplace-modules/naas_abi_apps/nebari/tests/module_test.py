"""Offline checks of the module: no broker, no engine."""

from __future__ import annotations

import asyncio

from naas_abi_apps.common.testing import fake_engine, no_core_import
from naas_abi_apps.nebari import MODULE_ID, ABIModule
from naas_abi_apps.nebari.agents.NebariAgent import INTENTS, NAME


def test_the_module_declares_its_agent_services_and_ontologies() -> None:
    assert ABIModule.module_id == MODULE_ID == "applications.nebari"
    assert [agent.name for agent in ABIModule.agents] == [NAME]
    assert set(ABIModule.dependencies.services) == {
        "model_registry",
        "document",
        "triple_store",
    }
    sources = {o.source(MODULE_ID) for o in ABIModule.get_ontologies()}
    assert sources == {
        "module/applications.nebari/NebariOntology.ttl",
        "module/applications.nebari/NebariSparqlQueries.ttl",
    }


def test_on_initialized_exposes_the_knowledge_agent() -> None:
    module = ABIModule(fake_engine(), ABIModule.Configuration())

    asyncio.run(module.on_initialized())

    assert set(module._agent_handlers) == {NAME}
    assert len(INTENTS) == 42


def test_the_module_never_imports_abi_core() -> None:
    assert (
        no_core_import("naas_abi_apps.nebari", "naas_abi_apps.nebari.__main__") is None
    )
