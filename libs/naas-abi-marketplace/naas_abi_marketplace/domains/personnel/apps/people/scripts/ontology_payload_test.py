"""Tests for the personnel ontology viewer payload."""

from __future__ import annotations

from naas_abi_marketplace.domains.personnel.apps.people.scripts.ontology_payload import (
    build_ontology_payload,
)


class TestOntologyPayload:
    def test_bundle_includes_core_module_and_process_slices(self) -> None:
        payload = build_ontology_payload()
        names = {source["name"] for source in payload["sources"]}
        assert "PersonnelOntology.ttl" in names
        assert "ActOfWorkingProcess.ttl" in names
        assert "@prefix" in payload["display_ttl"]

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
