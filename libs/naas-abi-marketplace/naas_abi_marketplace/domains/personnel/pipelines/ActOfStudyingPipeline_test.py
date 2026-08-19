"""Tests for ActOfStudyingPipeline."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

from naas_abi.ontologies.modules.ABIOntology import Site
from naas_abi_marketplace.domains.personnel.ontologies.modules.PersonnelOntology import (
    AcademicDegree,
    EnrollmentRecord,
    StudentRole,
)
from naas_abi_marketplace.domains.personnel.ontologies.processes.ActOfStudyingProcess import (
    ActOfStudying,
)
from naas_abi_marketplace.domains.personnel.ontologies.processes.ActOfWorkingProcess import (
    ProfileDocument,
    Skill,
)
from naas_abi_marketplace.domains.personnel.pipelines.ActOfStudyingPipeline import (
    ActOfStudyingPipeline,
    ActOfStudyingPipelineConfiguration,
    ActOfStudyingPipelineParameters,
)
from rdflib import URIRef
from rdflib.namespace import RDF

ABI_ORGANIZATION = URIRef("http://ontology.naas.ai/abi/Organization")
ABI_PERSON = URIRef("http://ontology.naas.ai/abi/Person")
ABI_TEMPORAL_REGION = URIRef("http://ontology.naas.ai/abi/TemporalRegion")
CCO_EDUCATIONAL_ORG = URIRef("https://www.commoncoreontologies.org/ont00000564")
PERSONNEL_ACTIVITIES = URIRef("http://ontology.naas.ai/personnel/activities_content")
PERSONNEL_HAS_ACT_OF_STUDYING = URIRef("http://ontology.naas.ai/personnel/hasActOfStudying")
PERSONNEL_SITE = URIRef(Site._class_uri)


def _studying_params(**overrides: object) -> ActOfStudyingPipelineParameters:
    base = {
        "first_name": "Alice",
        "last_name": "Dupont",
        "organization": "Demo University",
        "program": "Master's Degree, Business Administration",
        "site": "Paris",
        "start": date(2012, 9, 1),
        "end": date(2016, 6, 30),
        "duration": "2012 – 2016",
        "skills": ["Statistics"],
        "source_url": "https://demo.example/profiles/alice-dupont/education",
        "activities": None,
    }
    base.update(overrides)
    return ActOfStudyingPipelineParameters(**base)


def _types(graph) -> set[URIRef]:
    return {o for _, _, o in graph.triples((None, RDF.type, None)) if isinstance(o, URIRef)}


def test_run_emits_act_of_studying_and_seven_bucket_individuals() -> None:
    pipeline = ActOfStudyingPipeline(
        ActOfStudyingPipelineConfiguration(triple_store=None, persist=False)
    )

    graph = pipeline.run(_studying_params())

    types = _types(graph)
    assert URIRef(ActOfStudying._class_uri) in types
    assert URIRef(StudentRole._class_uri) in types
    assert URIRef(EnrollmentRecord._class_uri) in types
    assert URIRef(AcademicDegree._class_uri) in types
    assert URIRef(Skill._class_uri) in types
    assert URIRef(ProfileDocument._class_uri) in types
    assert ABI_PERSON in types
    assert ABI_ORGANIZATION in types
    assert CCO_EDUCATIONAL_ORG in types
    assert PERSONNEL_SITE in types
    assert ABI_TEMPORAL_REGION in types
    assert any(p == PERSONNEL_HAS_ACT_OF_STUDYING for _, p, _ in graph.triples((None, None, None)))


def test_run_stores_activities_on_enrollment_record() -> None:
    pipeline = ActOfStudyingPipeline(
        ActOfStudyingPipelineConfiguration(triple_store=None, persist=False)
    )

    graph = pipeline.run(
        _studying_params(activities="President of the student association")
    )

    assert any(p == PERSONNEL_ACTIVITIES for _, p, _ in graph.triples((None, None, None)))


def test_run_persists_delta_to_triple_store() -> None:
    triple_store = MagicMock()
    pipeline = ActOfStudyingPipeline(
        ActOfStudyingPipelineConfiguration(
            triple_store=triple_store,
            persist=True,
        )
    )

    pipeline.run(_studying_params())

    triple_store.insert.assert_called_once()
    inserted_graph, kwargs = triple_store.insert.call_args
    assert len(inserted_graph[0]) > 0
    assert "graph_name" in kwargs


def test_run_skips_persist_when_disabled() -> None:
    triple_store = MagicMock()
    pipeline = ActOfStudyingPipeline(
        ActOfStudyingPipelineConfiguration(
            triple_store=triple_store,
            persist=False,
        )
    )

    pipeline.run(_studying_params())

    triple_store.insert.assert_not_called()


def test_as_tools_exposes_register_act_of_studying() -> None:
    pipeline = ActOfStudyingPipeline(
        ActOfStudyingPipelineConfiguration(triple_store=None, persist=False)
    )

    tools = pipeline.as_tools()

    assert len(tools) == 1
    assert tools[0].name == "register_act_of_studying"
