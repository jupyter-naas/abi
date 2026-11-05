"""Offline checks of the module: no broker, no engine."""

from __future__ import annotations

import asyncio

from naas_abi_apps.common.testing import bound_tool_names, fake_engine, no_core_import
from naas_abi_apps.exchangeratesapi import MODULE_ID, ABIModule
from naas_abi_apps.exchangeratesapi.agents.ExchangeRatesAPIAgent import NAME


def test_the_module_declares_its_agent_and_services() -> None:
    assert ABIModule.module_id == MODULE_ID == "applications.exchangeratesapi"
    assert [agent.name for agent in ABIModule.agents] == [NAME]
    assert set(ABIModule.dependencies.services) == {
        "model_registry",
        "secret",
        "document",
    }


def test_on_initialized_binds_the_tools_from_the_secrets() -> None:
    engine = fake_engine({"EXCHANGERATESAPI_API_KEY": "x"})
    module = ABIModule(engine, ABIModule.Configuration())

    asyncio.run(module.on_initialized())

    assert set(module._agent_handlers) == {NAME}
    assert any(
        name.startswith("exchangeratesapi_") for name in bound_tool_names(engine)
    )


def test_without_secrets_the_agent_has_no_tools_of_its_own() -> None:
    engine = fake_engine()
    module = ABIModule(engine, ABIModule.Configuration())

    asyncio.run(module.on_initialized())

    assert not any(
        name.startswith("exchangeratesapi_") for name in bound_tool_names(engine)
    )


def test_the_module_never_imports_abi_core() -> None:
    assert (
        no_core_import(
            "naas_abi_apps.exchangeratesapi",
            "naas_abi_apps.exchangeratesapi.__main__",
            "naas_abi_apps.exchangeratesapi.integrations.ExchangeratesapiIntegration",
        )
        is None
    )
