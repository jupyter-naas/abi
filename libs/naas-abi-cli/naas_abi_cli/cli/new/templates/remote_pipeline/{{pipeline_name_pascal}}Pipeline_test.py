from __future__ import annotations

import asyncio

from rdflib import RDFS, Literal, URIRef

from .{{pipeline_name_pascal}}Pipeline import (
    {{pipeline_name_pascal}}Pipeline,
    {{pipeline_name_pascal}}PipelineConfiguration,
    {{pipeline_name_pascal}}PipelineParameters,
)


def test_the_pipeline_returns_a_graph() -> None:
    pipeline = {{pipeline_name_pascal}}Pipeline({{pipeline_name_pascal}}PipelineConfiguration())

    graph = asyncio.run(
        pipeline.run(
            {{pipeline_name_pascal}}PipelineParameters(iri="urn:test:a", label="A")
        )
    )

    assert (URIRef("urn:test:a"), RDFS.label, Literal("A")) in graph


def test_the_pipeline_is_named_after_its_class() -> None:
    assert {{pipeline_name_pascal}}Pipeline.slug() == "{{pipeline_name_snake}}_pipeline"
