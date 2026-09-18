"""Tests for Nexus-aligned BFO bucket resolution."""

from __future__ import annotations

from naas_abi_marketplace.domains.personnel.apps.people.bfo_bucket_resolution import (
    find_bfo_bucket_root_iri,
    infer_cockpit_bfo_bucket,
    load_bucket_inference_graph,
)


class TestBfoBucketResolution:
    def test_employee_role_maps_to_realizable(self) -> None:
        graph = load_bucket_inference_graph()
        iri = "http://ontology.naas.ai/personnel/EmployeeRole"
        assert infer_cockpit_bfo_bucket(graph, iri) == "Realizable"
        assert find_bfo_bucket_root_iri(graph, iri) == "http://purl.obolibrary.org/obo/BFO_0000017"

    def test_abi_person_maps_to_material_entity(self) -> None:
        graph = load_bucket_inference_graph()
        iri = "http://ontology.naas.ai/abi/Person"
        assert infer_cockpit_bfo_bucket(graph, iri) == "Material Entity"

    def test_act_of_working_maps_to_process(self) -> None:
        graph = load_bucket_inference_graph()
        iri = "http://ontology.naas.ai/personnel/ActOfWorking"
        assert infer_cockpit_bfo_bucket(graph, iri) == "Process"
