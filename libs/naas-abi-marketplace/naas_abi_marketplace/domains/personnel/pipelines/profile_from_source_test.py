"""Tests for profile-from-source orchestration."""

from __future__ import annotations

import json

from naas_abi_marketplace.domains.personnel.paths import DEMO_SOURCE_DIR
from naas_abi_marketplace.domains.personnel.person_sources import (
    load_person_sources,
    payload_to_profile_source_parameters,
)
from naas_abi_marketplace.domains.personnel.pipelines.profile_from_source import (
    ProfileFromSourcePipeline,
    ProfileFromSourcePipelineConfiguration,
)
from rdflib import URIRef
from rdflib.namespace import RDF

PERSONNEL_ACT_OF_WORKING = URIRef("http://ontology.naas.ai/personnel/ActOfWorking")
PERSONNEL_PROFILE_SUMMARY = URIRef("http://ontology.naas.ai/personnel/ProfileSummary")
ABI_PERSON = URIRef("http://ontology.naas.ai/abi/Person")


def test_register_profile_from_source_builds_working_and_summary() -> None:
    payloads = load_person_sources(DEMO_SOURCE_DIR)
    alice = next(
        p for p in payloads if p.get("profile", {}).get("slug") == "alice_dupont"
    )
    params = payload_to_profile_source_parameters(alice)

    pipeline = ProfileFromSourcePipeline(
        ProfileFromSourcePipelineConfiguration(persist=False)
    )
    graph = pipeline.run(params)

    assert len(graph) > 0
    persons = list(graph.subjects(RDF.type, ABI_PERSON))
    assert persons
    assert any(graph.triples((None, RDF.type, PERSONNEL_ACT_OF_WORKING)))
    assert any(graph.triples((None, RDF.type, PERSONNEL_PROFILE_SUMMARY)))


def test_payload_converter_roundtrip_json_shape() -> None:
    path = DEMO_SOURCE_DIR / "alice_dupont" / "index.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    params = payload_to_profile_source_parameters(payload)
    assert params.person.first_name == "Alice"
    assert params.profile is not None
    assert params.profile.slug == "alice_dupont"
    assert len(params.records) >= 2


def _payload_with_certifications() -> dict:
    return {
        "person": {
            "first_name": "Ada",
            "last_name": "Lovelace",
            "linkedin_profile_url": "https://example.test/ada",
        },
        "records": [],
        "profile": {
            "slug": "ada_lovelace",
            "certifications": [
                {"name": "Certified Auditor", "issuer": "ISACA"},
                {"name": "Chartered Accountant"},
            ],
        },
    }


def test_each_certification_is_an_act_of_certification_with_one_credential() -> None:
    params = payload_to_profile_source_parameters(_payload_with_certifications())
    graph = ProfileFromSourcePipeline(
        ProfileFromSourcePipelineConfiguration(persist=False)
    ).run(params)

    act = URIRef("http://ontology.naas.ai/personnel/ActOfCertification")
    certification = URIRef("http://ontology.naas.ai/personnel/Certification")
    assert len(list(graph.subjects(RDF.type, act))) == 2
    assert len(list(graph.subjects(RDF.type, certification))) == 2


def test_the_certification_names_the_page_it_was_published_on() -> None:
    params = payload_to_profile_source_parameters(_payload_with_certifications())
    graph = ProfileFromSourcePipeline(
        ProfileFromSourcePipelineConfiguration(persist=False)
    ).run(params)

    sourced = URIRef("http://ontology.naas.ai/personnel/isSourcedFrom")
    certification = URIRef("http://ontology.naas.ai/personnel/Certification")
    for subject in graph.subjects(RDF.type, certification):
        assert list(graph.objects(subject, sourced)), subject
