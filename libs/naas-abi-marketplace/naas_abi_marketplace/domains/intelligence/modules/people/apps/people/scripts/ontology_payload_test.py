"""Tests for the people ontology viewer payload."""

from __future__ import annotations

from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts.ontology_payload import (
    build_ontology_payload,
    load_people_schema_graph,
)
from naas_abi_marketplace.domains.intelligence.modules.people.utils.paths import (
    ONTOLOGIES_DIR,
)
from rdflib import OWL, Graph, URIRef
from rdflib.compare import isomorphic


class TestOntologyPayload:
    def test_bundle_includes_core_module_and_process_slices(self) -> None:
        payload = build_ontology_payload()
        names = {source["name"] for source in payload["sources"]}
        assert "PeopleOntology.ttl" in names
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
        union = load_people_schema_graph()
        # The same graph as the files taken together, not five files in a row.
        assert isomorphic(merged, union)
        text = payload["display_ttl"]
        # People terms are in the abi namespace: one prefix declaration for them.
        assert text.count("@prefix abi:") == 1
        # A class the slices restate is one block, not one per file.
        assert text.count("abi:Certification a owl:Class") == 1

    def test_no_connection_is_listed_twice(self) -> None:
        edges = build_ontology_payload()["graph"]["edges"]
        keys = [(e["from"], e["to"], e["kind"], e["label"]) for e in edges]
        assert len(keys) == len(set(keys))

    def test_the_profiling_act_is_in_the_graph(self) -> None:
        payload = build_ontology_payload()
        ids = {node["id"] for node in payload["graph"]["nodes"]}
        assert "abi:ActOfProfiling" in ids
        detail = payload["classes"]["http://ontology.naas.ai/abi/ActOfProfiling"]
        # its restriction points at the ProfileDocument declared in the working slice
        assert any(
            r["filler"] == "abi:ProfileDocument" for r in detail["restrictions"]
        )

    def test_the_where_of_each_act_is_a_geospatial_site_holding_its_facility(
        self,
    ) -> None:
        payload = build_ontology_payload()
        edges = payload["graph"]["edges"]

        def restricted(source: str, prop: str) -> list[str]:
            return [
                edge["to"]
                for edge in edges
                if edge["from"] == source
                and edge["kind"] == "restriction"
                and prop in edge["label"]
            ]

        for act in (
            "abi:ActOfWorking",
            "abi:ActOfStudying",
            "abi:ActOfCertification",
        ):
            assert restricted(act, "occursIn") == ["abi:GeospatialRegion"], act
        facilities = (
            "cco:ont00000468",  # Office Building
            "cco:ont00000270",  # Educational Facility
            "cco:ont00000192",  # Facility
        )
        for facility in facilities:
            # The building is a material entity located in the site.
            assert restricted(facility, "locatedIn") == ["abi:GeospatialLocation"]
        nodes = {node["id"]: node for node in payload["graph"]["nodes"]}
        for facility in facilities:
            assert nodes[facility]["label"] != facility.split(":")[-1]
            assert nodes[facility]["bfo_bucket"] == "Material Entity"
        assert nodes["cco:ont00000468"]["label"] == "Office Building"

    def test_people_and_organizations_are_tied_to_their_facilities(self) -> None:
        payload = build_ontology_payload()
        restrictions = {
            (edge["from"], edge["to"], edge["label"].split(" ")[0])
            for edge in payload["graph"]["edges"]
            if edge["kind"] == "restriction"
        }
        expected = {
            ("abi:Person", "cco:ont00000468", "abi:hasWorkFacility"),
            ("abi:Organization", "cco:ont00000468", "abi:hasOfficeBuilding"),
            ("abi:Person", "cco:ont00000270", "abi:hasStudyFacility"),
            ("cco:ont00000564", "cco:ont00000270", "abi:hasEducationalFacility"),
            ("abi:Person", "cco:ont00000192", "abi:hasCertificationFacility"),
            ("abi:Organization", "cco:ont00000192", "abi:hasAssessmentFacility"),
        }
        assert expected <= restrictions

    def test_every_facility_property_has_an_inverse_and_no_slice_asks_for_a_bare_site(
        self,
    ) -> None:
        graph = load_people_schema_graph()
        abi = "http://ontology.naas.ai/abi/"
        for name in (
            "WorkFacility",
            "StudyFacility",
            "CertificationFacility",
            "OfficeBuilding",
            "EducationalFacility",
            "AssessmentFacility",
        ):
            has = URIRef(f"{abi}has{name}")
            [inverse] = list(graph.objects(has, OWL.inverseOf))
            assert (inverse, OWL.inverseOf, has) in graph, name
        occurs_in = URIRef("http://ontology.naas.ai/abi/occursIn")
        site = URIRef("http://ontology.naas.ai/abi/Site")
        for restriction in graph.subjects(OWL.onProperty, occurs_in):
            assert (restriction, OWL.someValuesFrom, site) not in graph

    def test_language_capability_is_developed_by_working_studying_and_certification(
        self,
    ) -> None:
        payload = build_ontology_payload()
        developed_by = {
            edge["from"]
            for edge in payload["graph"]["edges"]
            if edge["kind"] == "restriction"
            and edge["to"] == "abi:LanguageCapability"
            and "developsLanguageCapability" in edge["label"]
        }
        assert developed_by == {
            "abi:ActOfWorking",
            "abi:ActOfStudying",
            "abi:ActOfCertification",
        }
        # a quality, like Skill, and stated from its own side too
        detail = payload["classes"]["http://ontology.naas.ai/abi/LanguageCapability"]
        assert detail["bfo_bucket"] == "Quality"
        assert any(
            r["property"] == "abi:isLanguageCapabilityDevelopedIn"
            for r in detail["restrictions"]
        )

    def test_stats_summarize_vocabulary_shape(self) -> None:
        payload = build_ontology_payload()
        stats = payload["stats"]
        assert stats["classes"] == len(payload["graph"]["nodes"])
        assert stats["restrictions"] > 0
        assert stats["object_properties"] > 0
        assert stats["datatype_properties"] > 0
        assert stats["annotation_properties"] > 0

    def test_occupation_role_is_in_the_graph(self) -> None:
        payload = build_ontology_payload()
        ids = {node["id"] for node in payload["graph"]["nodes"]}
        assert "abi:OccupationRole" in ids
        detail = payload["classes"]["http://ontology.naas.ai/abi/OccupationRole"]
        assert "Occupation" in detail["label"] or detail["label"] == "occupation role"

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
        role = payload["classes"]["http://ontology.naas.ai/abi/OccupationRole"]
        assert role["bfo_bucket"] == "Realizable"
        buckets = {node["bfo_bucket"] for node in payload["graph"]["nodes"]}
        assert "Unknown" not in buckets
