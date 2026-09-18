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
