"""Offline checks of the module: no broker, no engine."""

from __future__ import annotations

import asyncio

from naas_abi_apps.common.testing import (
    bound_tool_names,
    fake_engine,
    module_secrets,
    no_core_import,
)
from naas_abi_apps.github import MODULE_ID, ABIModule
from naas_abi_apps.github.agents.GitHubAgent import NAME
from naas_abi_apps.github.agents.GitHubAgentIntents import INTENTS
from naas_abi_apps.github.integrations.GitHubIntegration import READ_TOOLS


def test_the_module_declares_its_agent_services_and_ontology() -> None:
    assert ABIModule.module_id == MODULE_ID == "applications.github"
    assert [agent.name for agent in ABIModule.agents] == [NAME]
    assert set(ABIModule.dependencies.services) == {
        "model_registry",
        "document",
        "secret",
        "triple_store",
    }
    assert {o.source(MODULE_ID) for o in ABIModule.get_ontologies()} == {
        "module/applications.github/GitHubOntology.ttl"
    }


def test_with_the_token_the_agent_carries_its_read_tools() -> None:
    engine = fake_engine(
        module_secrets("applications.github", {"GITHUB_ACCESS_TOKEN": "t"})
    )
    module = ABIModule(engine, ABIModule.Configuration())

    asyncio.run(module.on_initialized())

    assert set(module._agent_handlers) == {NAME}
    bound = bound_tool_names(engine)
    assert READ_TOOLS <= bound
    assert not any(
        name.startswith("github_") and name not in READ_TOOLS for name in bound
    )


def test_with_its_write_tools_named_every_intent_has_its_tool() -> None:
    engine = fake_engine(
        module_secrets("applications.github", {"GITHUB_ACCESS_TOKEN": "t"})
    )
    writes = {i.intent_target for i in INTENTS} - READ_TOOLS
    module = ABIModule(
        engine,
        ABIModule.Configuration(
            agent_write_tools=",".join(sorted(writes)), repositories="o/app"
        ),
    )

    asyncio.run(module.on_initialized())

    assert {i.intent_target for i in INTENTS} <= bound_tool_names(engine)


def test_without_the_token_no_github_tools() -> None:
    engine = fake_engine()
    asyncio.run(ABIModule(engine, ABIModule.Configuration()).on_initialized())

    assert not any(name.startswith("github") for name in bound_tool_names(engine))


def test_the_module_never_imports_abi_core() -> None:
    assert (
        no_core_import(
            "naas_abi_apps.github",
            "naas_abi_apps.github.__main__",
            "naas_abi_apps.github.integrations.GitHubIntegration",
            "naas_abi_apps.github.integrations.GitHubGraphqlIntegration",
        )
        is None
    )
