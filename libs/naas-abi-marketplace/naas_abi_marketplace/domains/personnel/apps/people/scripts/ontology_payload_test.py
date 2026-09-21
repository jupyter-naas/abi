"""Tests for the personnel ontology viewer payload."""

from __future__ import annotations

from naas_abi_marketplace.domains.personnel.apps.people.scripts.ontology_payload import (
    build_ontology_payload,
    load_personnel_schema_graph,
)
from naas_abi_marketplace.domains.personnel.paths import ONTOLOGIES_DIR
from rdflib import Graph
from rdflib.compare import isomorphic


class TestOntologyPayload:
    def test_bundle_includes_core_module_and_process_slices(self) -> None:
        payload = build_ontology_payload()
        names = {source["name"] for source in payload["sources"]}
        assert "PersonnelOntology.ttl" in names
        assert "ActOfWorkingProcess.ttl" in names
        assert "@prefix" in payload["display_ttl"]

    def test_every_process_slice_is_in_the_bundle(self) -> None:
        payload = build_ontology_payload()
        names = {source["name"] for source in payload["sources"]}
        on_disk = {p.name for p in (ONTOLOGIES_DIR / "processes").glob("*.ttl")}
        assert on_disk <= names

    def test_the_merged_ontology_is_one_deduplicated_document(self) -> None:
        payload = build_ontology_payload()
        merged = Graph().parse(data=payload["display_ttl"], format="turtle")
        union = load_personnel_schema_graph()
        # The same graph as the files taken together, not five files in a row.
        assert isomorphic(merged, union)
        text = payload["display_ttl"]
        assert text.count("@prefix personnel:") == 1
        # A class the slices restate is one block, not one per file.
        assert text.count("personnel:Certification a owl:Class") == 1

    def test_no_connection_is_listed_twice(self) -> None:
        edges = build_ontology_payload()["graph"]["edges"]
        keys = [(e["from"], e["to"], e["kind"], e["label"]) for e in edges]
        assert len(keys) == len(set(keys))

    def test_the_profiling_act_is_in_the_graph(self) -> None:
        payload = build_ontology_payload()
        ids = {node["id"] for node in payload["graph"]["nodes"]}
        assert "personnel:ActOfPersonnelProfiling" in ids
        detail = payload["classes"][
            "http://ontology.naas.ai/personnel/ActOfPersonnelProfiling"
        ]
        # its restriction points at the ProfileDocument declared in the working slice
        assert any(
            r["filler"] == "personnel:ProfileDocument" for r in detail["restrictions"]
        )

    def test_stats_summarize_vocabulary_shape(self) -> None:
        payload = build_ontology_payload()
        stats = payload["stats"]
        assert stats["classes"] == len(payload["graph"]["nodes"])
        assert stats["restrictions"] > 0
        assert stats["object_properties"] > 0
        assert stats["datatype_properties"] > 0
        assert stats["annotation_properties"] > 0

    def test_employee_role_is_in_the_graph(self) -> None:
        payload = build_ontology_payload()
        ids = {node["id"] for node in payload["graph"]["nodes"]}
        assert "personnel:EmployeeRole" in ids
        detail = payload["classes"][
            "http://ontology.naas.ai/personnel/EmployeeRole"
        ]
        assert detail["label"] == "employee role" or "Employee" in detail["label"]

    def test_restrictions_surface_as_edges(self) -> None:
        payload = build_ontology_payload()
        kinds = {edge["kind"] for edge in payload["graph"]["edges"]}
        assert "subClassOf" in kinds
        assert "restriction" in kinds or "objectProperty" in kinds

    def test_classes_expose_bfo_bucket_for_graph_colours(self) -> None:
        payload = build_ontology_payload()
        for node in payload["graph"]["nodes"]:
            assert isinstance(node.get("bfo_bucket"), str) and node["bfo_bucket"]
            detail = payload["classes"][node["iri"]]
            assert detail["bfo_bucket"] == node["bfo_bucket"]
        role = payload["classes"]["http://ontology.naas.ai/personnel/EmployeeRole"]
        assert role["bfo_bucket"] == "Realizable"
        buckets = {node["bfo_bucket"] for node in payload["graph"]["nodes"]}
        assert "Unknown" not in buckets
