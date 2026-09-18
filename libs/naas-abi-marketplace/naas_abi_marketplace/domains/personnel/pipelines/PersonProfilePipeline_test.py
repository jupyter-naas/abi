"""Tests for PersonProfilePipeline."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

from naas_abi.ontologies.modules.ABIOntology import Site
from naas_abi_marketplace.domains.personnel.ontologies.modules.PersonnelOntology import (
    Certification,
    Grade,
    Interest,
    LanguageCapability,
    Portrait,
    ProfileSummary,
    Recommendation,
    ServiceLine,
)
from naas_abi_marketplace.domains.personnel.pipelines.PersonProfilePipeline import (
    PersonProfilePipeline,
    PersonProfilePipelineConfiguration,
    PersonProfilePipelineParameters,
)
from rdflib import URIRef
from rdflib.namespace import RDF

ABI_HAS_MEMBER_PART = URIRef("http://ontology.naas.ai/abi/hasMemberPart")
ABI_PERSON = URIRef("http://ontology.naas.ai/abi/Person")
PERSONNEL_COUNTRY_CODE = URIRef("http://ontology.naas.ai/personnel/country_code")
PERSONNEL_PROFILE_SLUG = URIRef("http://ontology.naas.ai/personnel/profile_slug")
PERSONNEL_SITE = URIRef(Site._class_uri)
PERSONNEL_YEARS = URIRef("http://ontology.naas.ai/personnel/years_of_experience")


def _profile_params(**overrides: object) -> PersonProfilePipelineParameters:
    base: dict[str, object] = {
        "first_name": "Alice",
        "last_name": "Dupont",
        "slug": "alice_dupont",
        "headline": "COO, Demo",
        "about": "Leads platform operations and agent orchestration.",
        "years_of_experience": 12,
        "organization": "Demo",
        "service_line": "Operations",
        "grade": "Partner",
        "office": "Paris La Défense",
        "city": "Paris",
        "country": "France",
        "country_code": "fr",
        "photo_url": "https://demo.example/profiles/alice_dupont/photo.jpg",
        "source_url": "https://demo.example/profiles/alice_dupont",
    }
    base.update(overrides)
    return PersonProfilePipelineParameters(**base)


def _pipeline(**overrides: object) -> PersonProfilePipeline:
    config: dict[str, object] = {"triple_store": None, "persist": False}
    config.update(overrides)
    return PersonProfilePipeline(PersonProfilePipelineConfiguration(**config))


def _types(graph) -> set[URIRef]:
    return {
        o for _, _, o in graph.triples((None, RDF.type, None)) if isinstance(o, URIRef)
    }


def _predicates(graph) -> set[URIRef]:
    return {p for _, p, _ in graph.triples((None, None, None))}


def test_run_emits_person_level_individuals() -> None:
    graph = _pipeline().run(_profile_params())

    types = _types(graph)
    assert ABI_PERSON in types
    assert URIRef(ProfileSummary._class_uri) in types
    assert URIRef(Portrait._class_uri) in types
    assert URIRef(ServiceLine._class_uri) in types
    assert URIRef(Grade._class_uri) in types
    assert PERSONNEL_SITE in types
    assert PERSONNEL_PROFILE_SLUG in _predicates(graph)


def test_years_of_experience_is_carried_by_the_summary() -> None:
    """It is a claim the source makes, not a figure counted from acts of working."""
    graph = _pipeline().run(_profile_params())

    subjects = list(graph.subjects(PERSONNEL_YEARS, None))
    assert len(subjects) == 1
    assert (subjects[0], RDF.type, URIRef(ProfileSummary._class_uri)) in graph


def test_country_code_is_upper_cased_on_the_site() -> None:
    graph = _pipeline().run(_profile_params(country_code="fr"))

    assert [str(o) for o in graph.objects(None, PERSONNEL_COUNTRY_CODE)] == ["FR"]


def test_person_is_a_member_part_of_the_service_line() -> None:
    """The facet must survive a person whose working history is not recorded."""
    graph = _pipeline().run(_profile_params())

    lines = list(graph.subjects(RDF.type, URIRef(ServiceLine._class_uri)))
    assert len(lines) == 1
    members = list(graph.objects(lines[0], ABI_HAS_MEMBER_PART))
    assert len(members) == 1


def test_service_line_needs_an_employer() -> None:
    """A service line with no parent organization is not what the source says."""
    graph = _pipeline().run(_profile_params(organization=None, service_line="Audit"))

    assert URIRef(ServiceLine._class_uri) not in _types(graph)


def test_optional_sections_are_written_when_given() -> None:
    graph = _pipeline().run(
        _profile_params(
            certifications=[
                {
                    "name": "Certified Demo Auditor",
                    "issuer": "Demo Institute",
                    "issue_date": date(2019, 6, 1),
                    "status": "active",
                }
            ],
            languages=[{"name": "Spanish", "proficiency": "Native or bilingual"}],
            interests=[{"name": "Ocean conservation", "kind": "topic"}],
            recommendations=[
                {
                    "author_first_name": "Bob",
                    "author_last_name": "Martin",
                    "content": "Rebuilt our close process in one quarter.",
                    "relationship": "Worked with Alice on the same team",
                    "written_on": date(2024, 11, 2),
                }
            ],
        )
    )

    types = _types(graph)
    assert URIRef(Certification._class_uri) in types
    assert URIRef(LanguageCapability._class_uri) in types
    assert URIRef(Interest._class_uri) in types
    assert URIRef(Recommendation._class_uri) in types


def test_empty_sections_emit_nothing() -> None:
    """No recommendations is an answer, not a gap to fill with an empty node."""
    graph = _pipeline().run(_profile_params())

    types = _types(graph)
    assert URIRef(Certification._class_uri) not in types
    assert URIRef(LanguageCapability._class_uri) not in types
    assert URIRef(Interest._class_uri) not in types
    assert URIRef(Recommendation._class_uri) not in types


def test_recommendation_carries_its_author() -> None:
    graph = _pipeline().run(
        _profile_params(
            recommendations=[
                {
                    "author_first_name": "Bob",
                    "author_last_name": "Martin",
                    "content": "Rebuilt our close process in one quarter.",
                }
            ]
        )
    )

    recommendations = list(graph.subjects(RDF.type, URIRef(Recommendation._class_uri)))
    assert len(recommendations) == 1
    authors = list(
        graph.objects(
            recommendations[0],
            URIRef("http://ontology.naas.ai/personnel/hasRecommendationAuthor"),
        )
    )
    assert len(authors) == 1
    assert (authors[0], RDF.type, ABI_PERSON) in graph


def test_no_portrait_without_a_url_or_path() -> None:
    graph = _pipeline().run(_profile_params(photo_url=None, photo_path=None))

    assert URIRef(Portrait._class_uri) not in _types(graph)


def test_run_persists_delta_to_triple_store() -> None:
    triple_store = MagicMock()

    _pipeline(triple_store=triple_store, persist=True).run(_profile_params())

    triple_store.insert.assert_called_once()
    inserted_graph, kwargs = triple_store.insert.call_args
    assert len(inserted_graph[0]) > 0
    assert "graph_name" in kwargs


def test_run_skips_persist_when_disabled() -> None:
    triple_store = MagicMock()

    _pipeline(triple_store=triple_store).run(_profile_params())

    triple_store.insert.assert_not_called()


def test_as_tools_exposes_register_person_profile() -> None:
    tools = _pipeline().as_tools()

    assert len(tools) == 1
    assert tools[0].name == "register_person_profile"
