"""Offline checks of the module: no broker, no engine."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from naas_abi_apps.common.runtime import configuration_from
from naas_abi_apps.common.testing import (
    FakeCache,
    FakeTripleStore,
    FakeVectorStore,
    fake_engine,
    no_core_import,
)
from naas_abi_apps.linkedin import EMBEDDINGS_WORKFLOW, MODULE_ID, ABIModule
from naas_abi_apps.linkedin.__main__ import ENV_PREFIX
from naas_abi_apps.linkedin.agents import LinkedInAgent, LinkedInKGAgent

QUERIES = {
    "linkedin_count_connections_by_person",
    "linkedin_search_connections_by_person",
    "linkedin_search_connections_by_organization",
    "linkedin_search_person_info",
}
SECRETS = {
    "li_at": "cookie",
    "JSESSIONID": '"ajax:1"',
    "LINKEDIN_PROFILE_URL": "https://www.linkedin.com/in/alice",
    "GOOGLE_CUSTOM_SEARCH_API_KEY": "key",
    "GOOGLE_CUSTOM_SEARCH_ENGINE_ID": "cx",
}


def engine_with(secrets: dict[str, str]):
    engine = fake_engine(secrets)
    engine.services.triple_store = FakeTripleStore()
    engine.services.vector_store = FakeVectorStore()
    engine.services.cache = FakeCache()
    return engine


@pytest.fixture
def agent_tools(monkeypatch) -> dict[str, set[str]]:
    """The tool names each agent is built with."""
    seen: dict[str, set[str]] = {}
    for agent in (LinkedInAgent, LinkedInKGAgent):
        real = agent.create_agent

        async def record(*args, tools, real=real, name=agent.NAME, **kwargs):
            seen[name] = {t.name for t in tools}
            return await real(*args, tools=tools, **kwargs)

        monkeypatch.setattr(agent, "create_agent", record)
    return seen


def test_the_module_declares_its_agents_workflow_and_queries() -> None:
    assert ABIModule.module_id == MODULE_ID == "applications.linkedin"
    assert [a.name for a in ABIModule.agents] == ["LinkedIn", "LinkedIn_KG"]
    assert set(ABIModule.dependencies.services) >= {
        "secret",
        "triple_store",
        "vector_store",
        "cache",
    }
    assert set(ABIModule.get_workflow_classes()) == {EMBEDDINGS_WORKFLOW}
    assert {o.source(MODULE_ID) for o in ABIModule.get_ontologies()} == {
        "module/applications.linkedin/LinkedInSparqlQueries.ttl"
    }


def test_the_configuration_comes_from_the_environment() -> None:
    default = configuration_from(ABIModule.Configuration, ENV_PREFIX, {})
    assert (default.li_at_secret, default.embed_at_start) == ("li_at", True)
    configured = configuration_from(
        ABIModule.Configuration,
        ENV_PREFIX,
        {"LINKEDIN_EMBED_AT_START": "false", "LINKEDIN_CHAT_MODEL": "m"},
    )
    assert (configured.embed_at_start, configured.chat_model) == (False, "m")


def test_without_secrets_the_agents_keep_the_graph_tools(agent_tools) -> None:
    engine = engine_with({})
    module = ABIModule(engine, ABIModule.Configuration())

    asyncio.run(module.on_initialized())

    assert set(module._agent_handlers) == {"LinkedIn", "LinkedIn_KG"}
    assert agent_tools["LinkedIn"] == QUERIES
    assert agent_tools["LinkedIn_KG"] == QUERIES | {
        "linkedin_search_person_uri",
        "linkedin_search_company_uri",
    }


def test_with_the_secrets_the_agent_has_linkedin_and_google_tools(agent_tools) -> None:
    module = ABIModule(engine_with(SECRETS), ABIModule.Configuration())

    asyncio.run(module.on_initialized())

    names = agent_tools["LinkedIn"]
    assert len([n for n in names if n.startswith("linkedin_get_")]) == 11
    assert {
        "linkedin_search_people",
        "googlesearch_search_linkedin_profile_page",
        "googlesearch_search_linkedin_organization_page",
    } <= names
    assert QUERIES <= names


def test_the_start_embeds_the_graph_names() -> None:
    engine = engine_with({})
    engine.services.triple_store.dataset.graph("urn:test").parse(
        Path(__file__).with_name("connections.ttl")
    )
    module = ABIModule(engine, ABIModule.Configuration())
    asyncio.run(module.on_initialized())

    asyncio.run(module.update_embeddings())

    collections = engine.services.vector_store.collections
    assert len(collections["linkedin_persons"]) == 3
    assert len(collections["linkedin_companies"]) == 2


def test_the_module_never_imports_abi_core() -> None:
    assert (
        no_core_import(
            "naas_abi_apps.linkedin",
            "naas_abi_apps.linkedin.__main__",
            "naas_abi_apps.linkedin.integrations.LinkedInIntegration",
        )
        is None
    )
