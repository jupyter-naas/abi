"""Tests for ``check_continuants_connected_to_process``.

Every continuant a domain ontology declares should be tied to a process, or it
floats free of everything that happens. The graphs here are small and spell out
the BFO roots they need, so no import has to resolve.
"""

from pathlib import Path

import pytest
import rdflib
from naas_abi_core.utils.onto2py.onto2py import (
    check_continuants_connected_to_process,
    continuants_without_process,
    restrictions_to_continuants_without_process,
)

PREFIXES = """
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix obo: <http://purl.obolibrary.org/obo/> .
@prefix ex: <http://example.org/> .

obo:BFO_0000015 a owl:Class .                                # process
obo:BFO_0000040 a owl:Class ; rdfs:subClassOf obo:BFO_0000002 .  # material entity
obo:BFO_0000019 a owl:Class ; rdfs:subClassOf obo:BFO_0000002 .  # quality
obo:BFO_0000002 a owl:Class .                                # continuant
obo:BFO_0000031 a owl:Class ; rdfs:subClassOf obo:BFO_0000002 .  # generically dependent continuant
obo:BFO_0000008 a owl:Class .                                # temporal region

ex:Act a owl:Class ; rdfs:subClassOf obo:BFO_0000015 .
ex:Person a owl:Class ; rdfs:subClassOf obo:BFO_0000040 .
ex:Skill a owl:Class ; rdfs:subClassOf obo:BFO_0000019 .
"""


def graph(extra: str) -> rdflib.Graph:
    return rdflib.Graph().parse(data=PREFIXES + extra, format="turtle")


def names(found: list[rdflib.URIRef]) -> list[str]:
    return [str(uri).rsplit("/", 1)[-1] for uri in found]


def test_a_continuant_alone_is_not_connected() -> None:
    assert names(continuants_without_process(graph(""))) == ["Person", "Skill"]


def test_a_restriction_on_the_continuant_naming_a_process_connects_it() -> None:
    g = graph(
        "ex:Skill rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:developedIn ;"
        " owl:someValuesFrom ex:Act ] ."
    )
    assert names(continuants_without_process(g)) == ["Person"]


def test_a_restriction_on_the_process_naming_the_continuant_connects_it() -> None:
    g = graph(
        "ex:Act rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:hasParticipant ;"
        " owl:someValuesFrom ex:Person ] ."
    )
    assert names(continuants_without_process(g)) == ["Skill"]


@pytest.mark.parametrize(
    "domain,range_",
    [("ex:Act", "ex:Skill"), ("ex:Skill", "ex:Act")],
)
def test_an_object_property_joining_them_connects_it_either_way(
    domain: str, range_: str
) -> None:
    g = graph(
        f"ex:joins a owl:ObjectProperty ; rdfs:domain {domain} ; rdfs:range {range_} ."
    )
    assert names(continuants_without_process(g)) == ["Person"]


def test_a_subclass_inherits_the_connection_of_its_parent() -> None:
    g = graph(
        """
        ex:Organization a owl:Class ; rdfs:subClassOf ex:Person .
        ex:Act rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:hasParticipant ;
                                 owl:someValuesFrom ex:Person ] .
        """
    )
    assert names(continuants_without_process(g)) == ["Skill"]


def test_a_process_restricting_on_a_bfo_root_does_not_connect_everything() -> None:
    g = graph(
        """
        ex:Act rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:hasParticipant ;
                                 owl:someValuesFrom obo:BFO_0000040 ] .
        """
    )
    assert names(continuants_without_process(g)) == ["Person", "Skill"]


def test_a_class_equivalent_to_a_bfo_root_is_a_root_too() -> None:
    g = graph(
        """
        ex:Quality a owl:Class ; owl:equivalentClass obo:BFO_0000019 .
        ex:Act rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:has ;
                                 owl:someValuesFrom ex:Quality ] .
        """
    )
    assert names(continuants_without_process(g)) == ["Person", "Skill"]


def test_processes_and_temporal_regions_are_not_continuants() -> None:
    g = graph("ex:Week a owl:Class ; rdfs:subClassOf obo:BFO_0000008 .")
    assert "Act" not in names(continuants_without_process(g))
    assert "Week" not in names(continuants_without_process(g))


def test_only_the_classes_asked_for_are_checked() -> None:
    g = graph("")
    person = rdflib.URIRef("http://example.org/Person")
    assert continuants_without_process(g, {person}) == [person]


def _ttl(tmp_path: Path, extra: str) -> str:
    path = tmp_path / "ontology.ttl"
    path.write_text(PREFIXES + extra)
    return str(path)


def test_the_check_raises_and_names_every_continuant_left_alone(tmp_path: Path) -> None:
    path = _ttl(tmp_path, "")
    with pytest.raises(ValueError) as error:
        check_continuants_connected_to_process(path)
    assert "ex:Person" in str(error.value)
    assert "ex:Skill" in str(error.value)
    assert "ex:Act" not in str(error.value)


def test_the_check_returns_the_errors_when_asked_not_to_raise(tmp_path: Path) -> None:
    issues = check_continuants_connected_to_process(
        _ttl(tmp_path, ""), raise_error=False
    )
    assert [i["subject"] for i in issues] == ["ex:Person", "ex:Skill"]
    assert {i["severity"] for i in issues} == {"ERROR"}
    assert {i["category"] for i in issues} == {"CONTINUANT_NOT_CONNECTED_TO_PROCESS"}


def test_the_check_passes_when_every_continuant_is_connected(tmp_path: Path) -> None:
    path = _ttl(
        tmp_path,
        """
        ex:Act rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:hasParticipant ;
                                 owl:someValuesFrom ex:Person ] ,
                               [ a owl:Restriction ; owl:onProperty ex:develops ;
                                 owl:someValuesFrom ex:Skill ] .
        """,
    )
    assert check_continuants_connected_to_process(path) == []


# A skill the act develops, sourced from a document nothing ties to a process.
SOURCED_FROM = """
ex:Doc a owl:Class ; rdfs:subClassOf obo:BFO_0000031 .
ex:Skill rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:developedIn ;
                           owl:someValuesFrom ex:Act ] ,
                         [ a owl:Restriction ; owl:onProperty ex:sourcedFrom ;
                           owl:someValuesFrom ex:Doc ] .
"""


def restricted(
    found: list[tuple[rdflib.URIRef, rdflib.URIRef, rdflib.URIRef]],
) -> list[tuple[str, str, str]]:
    return [tuple(str(term).rsplit("/", 1)[-1] for term in row) for row in found]  # type: ignore[misc]


def test_a_restriction_to_a_continuant_no_process_reaches_is_reported() -> None:
    found = restrictions_to_continuants_without_process(graph(SOURCED_FROM))
    assert restricted(found) == [("Skill", "sourcedFrom", "Doc")]


def test_the_restriction_passes_once_a_process_reaches_the_filler() -> None:
    g = graph(
        SOURCED_FROM
        + "ex:Act rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:cites ;"
        " owl:someValuesFrom ex:Doc ] ."
    )
    assert restrictions_to_continuants_without_process(g) == []


def test_a_filler_the_graph_knows_nothing_about_is_reported() -> None:
    g = graph(
        """
        ex:Skill rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:developedIn ;
                                   owl:someValuesFrom ex:Act ] ,
                                 [ a owl:Restriction ; owl:onProperty ex:sourcedFrom ;
                                   owl:someValuesFrom ex:Ghost ] .
        """
    )
    assert restricted(restrictions_to_continuants_without_process(g)) == [
        ("Skill", "sourcedFrom", "Ghost")
    ]


def test_restrictions_on_a_process_and_to_non_continuants_are_not_reported() -> None:
    g = graph(
        """
        ex:Week a owl:Class ; rdfs:subClassOf obo:BFO_0000008 .
        ex:Act rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:occupies ;
                                 owl:someValuesFrom ex:Week ] .
        ex:Skill rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:developedIn ;
                                   owl:someValuesFrom ex:Act ] ,
                                 [ a owl:Restriction ; owl:onProperty ex:during ;
                                   owl:someValuesFrom ex:Week ] ,
                                 [ a owl:Restriction ; owl:onProperty ex:is ;
                                   owl:someValuesFrom obo:BFO_0000019 ] .
        """
    )
    assert restrictions_to_continuants_without_process(g) == []


def test_only_the_subjects_asked_for_are_checked() -> None:
    g = graph(SOURCED_FROM)
    assert (
        restrictions_to_continuants_without_process(
            g, {rdflib.URIRef("http://example.org/Person")}
        )
        == []
    )


def test_the_check_reports_the_restriction_too(tmp_path: Path) -> None:
    path = _ttl(
        tmp_path,
        SOURCED_FROM
        + "ex:Act rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:hasParticipant ;"
        " owl:someValuesFrom ex:Person ] .",
    )
    issues = check_continuants_connected_to_process(path, raise_error=False)
    by_category = {i["category"]: i["subject"] for i in issues}
    # Doc is declared, and nothing ties it to a process: it is reported itself and by the restriction
    assert by_category["CONTINUANT_NOT_CONNECTED_TO_PROCESS"] == "ex:Doc"
    assert (
        by_category["RESTRICTION_TO_CONTINUANT_NOT_CONNECTED_TO_PROCESS"]
        == "ex:Skill ex:sourcedFrom"
    )
    with pytest.raises(ValueError, match="ex:Skill ex:sourcedFrom"):
        check_continuants_connected_to_process(path)
