"""Ontology routes keep request values as data.

``class_iris`` reach SPARQL only as validated IRIs, and an imported ontology
is parsed by rdflib in a worker, off the event loop, in time linear in its size.
"""

from __future__ import annotations

import asyncio
import time

import pytest
from naas_abi.apps.nexus.apps.api.app.services.ontology import service as ontology_service
from naas_abi.apps.nexus.apps.api.app.services.ontology.ontology__schema import (
    OntologyParseError,
    OntologyQueryError,
)
from naas_abi.apps.nexus.apps.api.app.services.ontology.service import OntologyService

TTL = b"""
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix dc: <http://purl.org/dc/elements/1.1/> .
@prefix ex: <http://example.com/onto/> .

<http://example.com/onto> dc:title "Example ontology" .
ex:Person a owl:Class ;
    rdfs:label "Person" ;
    skos:definition "A human being." ;
    skos:example "Ada" .
ex:Thing a owl:Class .
ex:knows a owl:ObjectProperty ;
    rdfs:label "knows" ;
    skos:definition "Is acquainted with." .
""".decode()


@pytest.mark.parametrize(
    "value",
    [
        "urn:a> } SERVICE <http://127.0.0.1:1/> { ?s ?p ?o",
        "urn:a>",
        "urn:a b",
        "",
        'urn:"x"',
    ],
)
def test_ontology_queries_keep_class_iris_to_iris(value: str) -> None:
    with pytest.raises(OntologyQueryError):
        ontology_service._class_iri_values(["http://example.com/onto/Person", value])


def test_ontology_queries_still_take_iris() -> None:
    assert (
        ontology_service._class_iri_values(["http://example.com/onto/Person", "urn:x:y"])
        == "<http://example.com/onto/Person> <urn:x:y>"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["get_class_parents", "get_subclassof_hierarchy"])
async def test_ontology_routes_keep_class_iris_to_iris_before_loading(method: str) -> None:
    service = OntologyService()

    async def unreachable(**_kwargs):
        raise AssertionError("the catalog is not read for a refused request")

    service.list_ontology_files = unreachable  # type: ignore[method-assign]
    with pytest.raises(OntologyQueryError):
        await getattr(service, method)(
            class_iris=["urn:a> } SERVICE <http://127.0.0.1:1/> {"], ontology_path="x.ttl"
        )


def test_ontology_import_keeps_what_the_file_declares() -> None:
    ontology = ontology_service._parse_ontology(TTL, "uploads/example.ttl")
    assert ontology.name == "Example ontology"
    assert [(c.iri, c.label, c.definition, c.examples) for c in ontology.classes] == [
        ("http://example.com/onto/Person", "Person", "A human being.", "Ada"),
        ("http://example.com/onto/Thing", "Thing", None, None),
    ]
    assert [(p.iri, p.label, p.definition) for p in ontology.properties] == [
        ("http://example.com/onto/knows", "knows", "Is acquainted with.")
    ]


@pytest.mark.asyncio
async def test_ontology_import_keeps_to_linear_parsing() -> None:
    """Many class headers whose bodies never close are refused quickly."""
    body = (
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        + "<http://e/x> a owl:Class ; " * 40_000
        + "x" * 1_000_000
    )
    started = time.monotonic()
    with pytest.raises(OntologyParseError):
        await OntologyService().import_ontology(body, "slow.ttl")
    assert time.monotonic() - started < 30


@pytest.mark.asyncio
async def test_ontology_import_keeps_the_event_loop_free(monkeypatch) -> None:
    def slow_parse(content: str, file_path: str):
        time.sleep(1.0)
        return ontology_service._reference_ontology_from_graph(ontology_service.Graph(), file_path)

    monkeypatch.setattr(ontology_service, "_parse_ontology", slow_parse)
    ticks = 0

    async def ticker() -> None:
        nonlocal ticks
        while True:
            await asyncio.sleep(0.05)
            ticks += 1

    task = asyncio.create_task(ticker())
    await OntologyService().import_ontology("", "empty.ttl")
    task.cancel()
    assert ticks >= 10


RDF_XML = """<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
         xmlns:owl="http://www.w3.org/2002/07/owl#"
         xmlns:dc="http://purl.org/dc/elements/1.1/">
  <owl:Ontology rdf:about="http://example.com/onto">
    <dc:title>XML ontology</dc:title>
  </owl:Ontology>
  <owl:Class rdf:about="http://example.com/onto/Person">
    <rdfs:label>Person</rdfs:label>
    <dc:title>A class title, not the ontology's</dc:title>
  </owl:Class>
  <owl:ObjectProperty rdf:about="http://example.com/onto/knows">
    <rdfs:label>knows</rdfs:label>
  </owl:ObjectProperty>
</rdf:RDF>
"""


@pytest.mark.parametrize("name", ["people.owl", "people.rdf"])
def test_ontology_import_keeps_the_format_of_the_file_name(name: str) -> None:
    ontology = ontology_service._parse_ontology(RDF_XML, f"uploads/{name}")
    assert ontology.name == "XML ontology"
    assert ontology.format == name.rsplit(".", 1)[1]
    assert [(c.iri, c.label) for c in ontology.classes] == [
        ("http://example.com/onto/Person", "Person")
    ]
    assert [p.iri for p in ontology.properties] == ["http://example.com/onto/knows"]


def test_ontology_import_keeps_the_ontologys_own_title() -> None:
    """Another subject's title never names the ontology."""
    ttl = (
        TTL
        + '<http://example.com/onto/Person> <http://purl.org/dc/elements/1.1/title> "Aaa" .\n'
        + "<http://example.com/onto> a <http://www.w3.org/2002/07/owl#Ontology> .\n"
    )
    for _ in range(3):
        assert ontology_service._parse_ontology(ttl, "x.ttl").name == "Example ontology"


def test_ontology_import_still_reads_an_owl_file_in_turtle() -> None:
    ontology = ontology_service._parse_ontology(TTL, "uploads/example.owl")
    assert ontology.name == "Example ontology"
    assert len(ontology.classes) == 2


def test_ontology_import_names_an_untitled_ontology_after_its_file() -> None:
    ttl = "<http://e/A> a <http://www.w3.org/2002/07/owl#Class> ."
    assert ontology_service._parse_ontology(ttl, "uploads/my.onto.ttl").name == "my.onto"


def test_ontology_import_keeps_one_parse_for_other_formats(monkeypatch) -> None:
    calls: list[str] = []
    real = ontology_service.rdf_upload.parse_upload

    def counted(content, fmt, **kwargs):
        calls.append(fmt)
        return real(content, fmt, **kwargs)

    monkeypatch.setattr(ontology_service.rdf_upload, "parse_upload", counted)
    with pytest.raises(ontology_service.rdf_upload.RdfUploadError):
        ontology_service._parse_ontology("<not rdf/xml", "uploads/bad.rdf")
    assert calls == ["xml"]
    calls.clear()
    with pytest.raises(ontology_service.rdf_upload.RdfUploadError):
        ontology_service._parse_ontology("<not rdf/xml", "uploads/bad.owl")
    assert calls == ["xml", "turtle"]
