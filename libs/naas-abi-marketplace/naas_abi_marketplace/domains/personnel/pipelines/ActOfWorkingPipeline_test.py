"""Tests for ActOfWorkingPipeline."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

from naas_abi.ontologies.modules.ABIOntology import Site
from naas_abi_marketplace.domains.personnel.ontologies.processes.ActOfWorkingProcess import (
    ActOfWorking,
    Mission,
    ProfileDocument,
    Skill,
)
from naas_abi_marketplace.domains.personnel.pipelines.ActOfWorkingPipeline import (
    ActOfWorkingPipeline,
    ActOfWorkingPipelineConfiguration,
    ActOfWorkingPipelineParameters,
)
from rdflib import URIRef
from rdflib.namespace import RDF

ABI_ORGANIZATION = URIRef("http://ontology.naas.ai/abi/Organization")
ABI_PERSON = URIRef("http://ontology.naas.ai/abi/Person")
ABI_SITE = URIRef(Site._class_uri)
ABI_TEMPORAL_REGION = URIRef("http://ontology.naas.ai/abi/TemporalRegion")
PERSONNEL_HAS_ACT_OF_WORKING = URIRef("http://ontology.naas.ai/personnel/hasActOfWorking")
PERSONNEL_IS_SOURCED_FROM = URIRef("http://ontology.naas.ai/personnel/isSourcedFrom")


def _working_params(**overrides: object) -> ActOfWorkingPipelineParameters:
    base = {
        "first_name": "Florent",
        "last_name": "Ravenel",
        "organization": "naas.ai",
        "title": "Co-Founder & COO",
        "site": "World",
        "start": date(2023, 4, 1),
        "mission_label": "Lead the Universal Data & AI Platform",
        "mission": "Build agent ecosystems for organizations.",
        "contract_type": "Self-employed",
        "skills": ["Python (Programming Language)"],
        "source_url": "https://demo.example/profiles/demo",
    }
    base.update(overrides)
    return ActOfWorkingPipelineParameters(**base)


def _types(graph) -> set[URIRef]:
    return {o for _, _, o in graph.triples((None, RDF.type, None)) if isinstance(o, URIRef)}


def test_run_emits_act_of_working_and_seven_bucket_individuals() -> None:
    pipeline = ActOfWorkingPipeline(
        ActOfWorkingPipelineConfiguration(triple_store=None, persist=False)
    )

    graph = pipeline.run(_working_params())

    types = _types(graph)
    assert URIRef(ActOfWorking._class_uri) in types
    assert URIRef(Mission._class_uri) in types
    assert URIRef(Skill._class_uri) in types
    assert URIRef(ProfileDocument._class_uri) in types
    assert ABI_PERSON in types
    assert ABI_ORGANIZATION in types
    assert ABI_SITE in types
    assert ABI_TEMPORAL_REGION in types
    assert any(p == PERSONNEL_HAS_ACT_OF_WORKING for _, p, _ in graph.triples((None, None, None)))


def test_run_links_profile_document_to_mission() -> None:
    pipeline = ActOfWorkingPipeline(
        ActOfWorkingPipelineConfiguration(triple_store=None, persist=False)
    )

    graph = pipeline.run(_working_params())

    assert any(p == PERSONNEL_IS_SOURCED_FROM for _, p, _ in graph.triples((None, None, None)))


def test_run_persists_delta_to_triple_store() -> None:
    triple_store = MagicMock()
    pipeline = ActOfWorkingPipeline(
        ActOfWorkingPipelineConfiguration(
            triple_store=triple_store,
            persist=True,
        )
    )

    pipeline.run(_working_params())

    triple_store.insert.assert_called_once()
    inserted_graph, kwargs = triple_store.insert.call_args
    assert len(inserted_graph[0]) > 0
    assert "graph_name" in kwargs


def test_run_skips_persist_when_disabled() -> None:
    triple_store = MagicMock()
    pipeline = ActOfWorkingPipeline(
        ActOfWorkingPipelineConfiguration(
            triple_store=triple_store,
            persist=False,
        )
    )

    pipeline.run(_working_params())

    triple_store.insert.assert_not_called()


def test_as_tools_exposes_register_act_of_working() -> None:
    pipeline = ActOfWorkingPipeline(
        ActOfWorkingPipelineConfiguration(triple_store=None, persist=False)
    )

    tools = pipeline.as_tools()

    assert len(tools) == 1
    assert tools[0].name == "register_act_of_working"
