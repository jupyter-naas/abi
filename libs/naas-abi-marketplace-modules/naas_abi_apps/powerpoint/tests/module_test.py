"""Offline checks of the module: no broker, no engine."""

from __future__ import annotations

import asyncio

from naas_abi_apps.common.testing import (
    FakeTripleStore,
    bound_tool_names,
    fake_engine,
    no_core_import,
)
from naas_abi_apps.powerpoint import MODULE_ID, PIPELINE, WORKFLOW, ABIModule
from naas_abi_apps.powerpoint.agents.PowerPointAgent import NAME


def test_the_module_declares_its_agent_processes_and_ontologies() -> None:
    assert ABIModule.module_id == MODULE_ID == "applications.powerpoint"
    assert [agent.name for agent in ABIModule.agents] == [NAME]
    assert set(ABIModule.get_workflow_classes()) == {WORKFLOW}
    assert set(ABIModule.get_pipeline_classes()) == {PIPELINE}
    assert {o.source(MODULE_ID) for o in ABIModule.get_ontologies()} == {
        "module/applications.powerpoint/PowerPointOntology.ttl",
        "module/applications.powerpoint/PowerPointSparqlQueries.ttl",
    }


def test_on_initialized_binds_the_processes_and_the_tools() -> None:
    engine = fake_engine(
        {"NAAS_API_KEY": "k", "WORKSPACE_ID": "ws", "STORAGE_NAME": "st"}
    )
    engine.services.triple_store = FakeTripleStore()
    module = ABIModule(engine, ABIModule.Configuration())

    asyncio.run(module.on_initialized())

    assert set(module._agent_handlers) == {NAME}
    assert module.get_workflow_instance(WORKFLOW).configuration.naas is not None
    assert {
        "powerpoint_get_all_shapes_and_slides",
        "powerpoint_get_shapes_from_slide",
        "create_presentation_from_template",
        "add_powerpoint_presentation",
        "powerpoint_search_presentation_by_name",
    } <= bound_tool_names(engine)


def test_without_naas_secrets_decks_are_not_uploaded() -> None:
    engine = fake_engine()
    engine.services.triple_store = FakeTripleStore()
    module = ABIModule(engine, ABIModule.Configuration())

    asyncio.run(module.on_initialized())

    assert module.get_workflow_instance(WORKFLOW).configuration.naas is None


def test_the_module_never_imports_abi_core() -> None:
    assert (
        no_core_import("naas_abi_apps.powerpoint", "naas_abi_apps.powerpoint.__main__")
        is None
    )


def test_the_template_tool_returns_json_the_agent_can_read() -> None:
    import json
    from pathlib import Path

    from naas_abi_apps.powerpoint.integrations.PowerPointIntegration import (
        PowerPointIntegrationConfiguration,
        as_tools,
    )

    template = (
        Path(__file__).resolve().parents[1] / "templates" / "TemplateMinimal.pptx"
    ).read_bytes()
    tool = {
        t.name: t
        for t in as_tools(PowerPointIntegrationConfiguration(template=template))
    }["powerpoint_get_all_shapes_and_slides"]

    slides = asyncio.run(tool.ainvoke({}))

    json.dumps(slides)
    assert [s["slide_number"] for s in slides] == [0, 1, 2]
    assert slides[1]["shapes"][2] | {
        "left": None,
        "top": None,
        "width": None,
        "height": None,
    } == {
        "slide_number": 1,
        "shape_id": 4,
        "shape_type": 17,
        "shape_alt_text": "Body: bullet points, one per line",
        "text": "Content",
        "left": None,
        "top": None,
        "width": None,
        "height": None,
        "rotation": 0.0,
    }
