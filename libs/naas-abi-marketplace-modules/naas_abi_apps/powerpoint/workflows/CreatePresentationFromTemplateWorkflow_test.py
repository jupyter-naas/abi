"""Offline: the bundled template filled into a deck, stored, uploaded (fake
Naas) and added to a fake triple store, then found with a SPARQL template."""

from __future__ import annotations

import asyncio
import io

from naas_abi_apps.common.sparql_templates import module_queries, query_tools
from naas_abi_apps.common.testing import FakeTripleStore, MemoryStorage
from naas_abi_apps.powerpoint.pipelines.AddPowerPointPresentationPipeline import (
    TEMPLATES_DIR,
    AddPowerPointPresentationPipeline,
    AddPowerPointPresentationPipelineConfiguration,
)
from naas_abi_apps.powerpoint.workflows.CreatePresentationFromTemplateWorkflow import (
    CreatePresentationFromTemplateWorkflow,
    CreatePresentationFromTemplateWorkflowConfiguration,
    CreatePresentationFromTemplateWorkflowParameters,
)
from pptx import Presentation

SLIDES = [
    {
        "template_slide_number": 0,
        "shapes": [
            {"shape_id": 2, "text": "Q3 review"},
            {"shape_id": 4, "text": "2026-11-05"},
        ],
    },
    {
        "template_slide_number": 1,
        "shapes": [
            {"shape_id": 2, "text": "Revenue"},
            {"shape_id": 4, "text": "Up 12%\nChurn down"},
        ],
        "sources": ["https://example.com/report"],
    },
    {"template_slide_number": 1, "shapes": [{"shape_id": 2, "text": "Next steps"}]},
]


class FakeNaas:
    def __init__(self) -> None:
        self.uploads: list[dict] = []

    async def upload_asset(self, **kwargs):
        self.uploads.append(kwargs)
        return {"asset_url": f"https://naas.ai/assets/{kwargs['object_name']}"}


def setup(naas=None):
    store, storage = FakeTripleStore(), MemoryStorage()
    pipeline = AddPowerPointPresentationPipeline(
        AddPowerPointPresentationPipelineConfiguration(
            triple_store=store, storage=storage
        )
    )
    workflow = CreatePresentationFromTemplateWorkflow(
        CreatePresentationFromTemplateWorkflowConfiguration(
            storage=storage,
            pipeline=pipeline,
            naas=naas,
            workspace_id="ws",
            storage_name="st",
        )
    )
    return workflow, store, storage


def texts(slide) -> list[str]:
    return [shape.text_frame.text for shape in slide.shapes if shape.has_text_frame]


def test_the_deck_is_built_from_the_template_and_stored() -> None:
    workflow, _, storage = setup()

    result = asyncio.run(
        workflow.run(
            CreatePresentationFromTemplateWorkflowParameters(
                presentation_name="Q3", slides_data=SLIDES
            )
        )
    )

    assert result["presentation_name"] == "Q3.pptx" and result["download_url"] is None
    deck = Presentation(
        io.BytesIO(storage.objects[("powerpoint/presentations", "Q3.pptx")])
    )
    assert len(deck.slides) == 3
    assert "Q3 review" in texts(deck.slides[0]) and "2026-11-05" in texts(
        deck.slides[0]
    )
    assert any("Up 12%" in t for t in texts(deck.slides[1]))
    assert (
        "https://example.com/report" in deck.slides[1].notes_slide.notes_text_frame.text
    )


def test_the_deck_and_its_template_go_to_the_graph_once() -> None:
    workflow, store, _ = setup()
    parameters = CreatePresentationFromTemplateWorkflowParameters(
        presentation_name="Q3", slides_data=SLIDES
    )

    first = asyncio.run(workflow.run(parameters))
    second = asyncio.run(
        workflow.run(parameters.model_copy(update={"presentation_name": "Q4"}))
    )

    assert (
        first["template_uri"]
        and first["presentation_uri"]
        and first["presentation_uri"] != first["template_uri"]
    )
    # The template is the same presentation: found again, not added twice.
    assert second["template_uri"] == first["template_uri"]
    found = asyncio.run(
        {t.name: t for t in query_tools(module_queries(TEMPLATES_DIR.parent), store)}[
            "powerpoint_search_presentation_by_name"
        ].ainvoke({"presentation_name": "Q3"})
    )
    assert found and any("Q3" in str(row) for row in found)


def test_with_naas_the_deck_is_uploaded_for_a_download_url() -> None:
    naas = FakeNaas()
    workflow, _, _ = setup(naas)

    result = asyncio.run(
        workflow.run(
            CreatePresentationFromTemplateWorkflowParameters(
                presentation_name="Q3.pptx", slides_data=SLIDES[:1]
            )
        )
    )

    assert result["download_url"] == "https://naas.ai/assets/Q3.pptx"
    (upload,) = naas.uploads
    assert (upload["workspace_id"], upload["storage_name"], upload["prefix"]) == (
        "ws",
        "st",
        "assets",
    )


def test_a_template_from_object_storage_is_used_when_given() -> None:
    workflow, _, storage = setup()
    storage.objects[("templates", "brand.pptx")] = (
        TEMPLATES_DIR / "TemplateMinimal.pptx"
    ).read_bytes()

    result = asyncio.run(
        workflow.run(
            CreatePresentationFromTemplateWorkflowParameters(
                presentation_name="Brand",
                slides_data=SLIDES[:1],
                template_path="templates/brand.pptx",
            )
        )
    )

    assert result["storage_path"] == "powerpoint/presentations/Brand.pptx"
