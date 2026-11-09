"""Offline checks of the module: no broker, no engine."""

from __future__ import annotations

import asyncio

from naas_abi_apps.agicap import MODULE_ID, ABIModule
from naas_abi_apps.agicap.__main__ import ENV_PREFIX
from naas_abi_apps.agicap.agents.AgicapAgent import INTENTS, NAME
from naas_abi_apps.common.runtime import configuration_from
from naas_abi_apps.common.testing import bound_tool_names, fake_engine, no_core_import


def test_the_module_declares_its_agent_and_services() -> None:
    assert ABIModule.module_id == MODULE_ID == "applications.agicap"
    assert [agent.name for agent in ABIModule.agents] == [NAME]
    assert set(ABIModule.dependencies.services) == {
        "model_registry",
        "document",
        "secret",
    }


def test_the_configuration_names_the_secrets() -> None:
    configuration = configuration_from(
        ABIModule.Configuration, ENV_PREFIX, {"AGICAP_API_TOKEN_SECRET": "ACME_AGICAP"}
    )
    assert configuration.secret_names()["api_token"] == "ACME_AGICAP"
    assert configuration.secret_names()["username"] == "AGICAP_USERNAME"


def test_on_initialized_binds_tools_and_intents_from_the_secrets() -> None:
    engine = fake_engine({"AGICAP_API_TOKEN": "t", "AGICAP_BEARER_TOKEN": "b"})
    module = ABIModule(engine, ABIModule.Configuration())

    asyncio.run(module.on_initialized())

    assert set(module._agent_handlers) == {NAME}
    assert {"agicap_list_companies", "agicap_get_debts"} <= bound_tool_names(engine)
    assert {i.intent_target for i in INTENTS} <= bound_tool_names(engine)


def test_without_secrets_the_agent_has_no_agicap_tools() -> None:
    engine = fake_engine()
    module = ABIModule(engine, ABIModule.Configuration())

    asyncio.run(module.on_initialized())

    assert not any(name.startswith("agicap_") for name in bound_tool_names(engine))


def test_the_module_never_imports_abi_core() -> None:
    assert (
        no_core_import("naas_abi_apps.agicap", "naas_abi_apps.agicap.__main__") is None
    )
