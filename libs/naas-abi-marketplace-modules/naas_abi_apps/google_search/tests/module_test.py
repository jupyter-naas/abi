"""Offline checks of the module: no broker, no engine."""

from __future__ import annotations

import asyncio

from naas_abi_apps.common.testing import bound_tool_names, fake_engine, no_core_import
from naas_abi_apps.google_search import MODULE_ID, ABIModule
from naas_abi_apps.google_search.agents.GoogleSearchAgent import INTENTS, NAME

SECRETS = {"GOOGLE_CUSTOM_SEARCH_API_KEY": "k", "GOOGLE_CUSTOM_SEARCH_ENGINE_ID": "cx"}


def test_the_module_declares_its_agent_workflows_and_ontology() -> None:
    assert ABIModule.module_id == MODULE_ID == "applications.google_search"
    assert [agent.name for agent in ABIModule.agents] == [NAME]
    assert set(ABIModule.get_workflow_classes()) == {
        "search_linked_in_profile_page_workflow",
        "search_linked_in_organization_page_workflow",
    }
    assert {o.source(MODULE_ID) for o in ABIModule.get_ontologies()} == {
        "module/applications.google_search/GoogleSearchOntology.ttl"
    }


def test_with_the_secrets_every_intent_has_its_tool() -> None:
    engine = fake_engine(SECRETS)
    module = ABIModule(engine, ABIModule.Configuration())

    asyncio.run(module.on_initialized())

    assert set(module._agent_handlers) == {NAME}
    assert {i.intent_target for i in INTENTS} <= bound_tool_names(engine)
    workflow = module.get_workflow_instance("search_linked_in_profile_page_workflow")
    assert workflow.integration_configuration.api_key == "k"


def test_without_the_secrets_the_agent_loads_without_search_tools() -> None:
    engine = fake_engine()
    module = ABIModule(engine, ABIModule.Configuration())

    asyncio.run(module.on_initialized())

    assert not any(
        name.startswith("googlesearch_") for name in bound_tool_names(engine)
    )


def test_the_module_never_imports_abi_core() -> None:
    assert (
        no_core_import(
            "naas_abi_apps.google_search", "naas_abi_apps.google_search.__main__"
        )
        is None
    )
