"""Offline checks of the module: no broker, no engine."""

from __future__ import annotations

import asyncio

from naas_abi_apps.arxiv import MODULE_ID, ABIModule
from naas_abi_apps.arxiv.agents.ArXivAgent import NAME
from naas_abi_apps.common.testing import (
    FakeTripleStore,
    bound_tool_names,
    fake_engine,
    no_core_import,
)


def test_the_module_declares_its_agent_pipeline_services_and_ontology() -> None:
    assert ABIModule.module_id == MODULE_ID == "applications.arxiv"
    assert [agent.name for agent in ABIModule.agents] == [NAME]
    assert set(ABIModule.dependencies.services) == {
        "model_registry",
        "document",
        "triple_store",
        "object_storage",
    }
    assert set(ABIModule.get_pipeline_classes()) == {"ar_xiv_paper_pipeline"}
    assert {o.source(MODULE_ID) for o in ABIModule.get_ontologies()} == {
        "module/applications.arxiv/ArXivOntology.ttl"
    }


def test_on_initialized_binds_the_tools_of_the_in_engine_agent() -> None:
    engine = fake_engine()
    engine.services.triple_store = FakeTripleStore()
    module = ABIModule(engine, ABIModule.Configuration())

    asyncio.run(module.on_initialized())

    assert set(module._agent_handlers) == {NAME}
    assert {
        "search_arxiv_papers",
        "get_arxiv_paper",
        "arxiv_paper_pipeline",
        "query_arxiv_authors",
        "query_arxiv_papers",
        "get_frequent_authors",
        "get_arxiv_schema",
        "execute_arxiv_query",
    } <= bound_tool_names(engine)


def test_the_module_never_imports_abi_core() -> None:
    assert no_core_import("naas_abi_apps.arxiv", "naas_abi_apps.arxiv.__main__") is None
