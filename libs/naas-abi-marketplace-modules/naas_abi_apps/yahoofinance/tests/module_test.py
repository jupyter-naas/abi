"""Offline checks of the module: no broker, no engine."""

from __future__ import annotations

import asyncio

from naas_abi_apps.common.testing import bound_tool_names, fake_engine, no_core_import
from naas_abi_apps.yahoofinance import MODULE_ID, ABIModule
from naas_abi_apps.yahoofinance.agents.YfinanceAgent import INTENTS, NAME


def test_the_module_declares_its_agent_and_services() -> None:
    assert ABIModule.module_id == MODULE_ID == "applications.yahoofinance"
    assert [agent.name for agent in ABIModule.agents] == [NAME]
    assert set(ABIModule.dependencies.services) == {
        "model_registry",
        "document",
        "object_storage",
    }


def test_on_initialized_binds_every_tool_its_intents_name() -> None:
    engine = fake_engine()
    module = ABIModule(engine, ABIModule.Configuration())

    asyncio.run(module.on_initialized())

    assert set(module._agent_handlers) == {NAME}
    assert {i.intent_target for i in INTENTS} <= bound_tool_names(engine)


def test_the_module_never_imports_abi_core() -> None:
    assert (
        no_core_import(
            "naas_abi_apps.yahoofinance",
            "naas_abi_apps.yahoofinance.__main__",
            "naas_abi_apps.yahoofinance.integrations.YfinanceIntegration",
        )
        is None
    )
