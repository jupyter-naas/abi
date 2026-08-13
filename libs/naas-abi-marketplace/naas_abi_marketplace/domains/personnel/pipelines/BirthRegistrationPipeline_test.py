"""Unit tests for BirthRegistrationPipeline (in-memory triple store)."""

from __future__ import annotations

from rdflib import RDF, RDFS, Graph, URIRef
from rdflib.query import Result

from naas_abi_marketplace.domains.personnel.pipelines.BirthRegistrationPipeline import (
    CCO,
    PERSONNEL,
    BirthRegistrationPipeline,
    BirthRegistrationPipelineConfiguration,
    BirthRegistrationPipelineParameters,
)

PERSON = URIRef("http://ontology.naas.ai/abi/Person")
BIRTH = URIRef("https://www.commoncoreontologies.org/ont00001237")
BIRTH_RECORD = URIRef("http://ontology.naas.ai/personnel/BirthRecord")
DECLARATION = URIRef("http://ontology.naas.ai/personnel/BirthDeclarationAct")
REGISTRATION = URIRef("http://ontology.naas.ai/personnel/BirthRegistrationProcess")
DOCUMENT = URIRef("http://ontology.naas.ai/abi/DocumentContentEntity")


class _FakeTripleStore:
    """Minimal insert/query stand-in for pipeline unit tests."""

    def __init__(self) -> None:
        self.graph = Graph()

    def insert(self, triples: Graph, graph_name: URIRef) -> None:
        self.graph += triples

    def query(self, sparql: str) -> Result:
        import re

        # Drop GRAPH <iri> { ... } wrappers; keep nested braces intact.
        cleaned = re.sub(r"GRAPH\s*<[^>]+>\s*\{", "{", sparql)
        return self.graph.query(cleaned)


def _pipeline() -> tuple[BirthRegistrationPipeline, _FakeTripleStore]:
    store = _FakeTripleStore()
    pipe = BirthRegistrationPipeline(
        BirthRegistrationPipelineConfiguration(
            triple_store=store,  # type: ignore[arg-type]
            graph_name=URIRef("http://ontology.naas.ai/graph/personnel"),
            ontology_namespace="http://ontology.naas.ai/personnel/",
        )
    )
    return pipe, store


def test_register_jeremy_creates_four_birth_processes():
    """Florent registers Jeremy (Vitré, 05/12/1989) from Pascal & Christine → 4 Births."""
    pipe, store = _pipeline()
    graph = pipe.run(
        BirthRegistrationPipelineParameters(
            first_name="Jeremy",
            last_name="Ravenel",
            birth_date="05/12/1989",
            birth_site="Vitré",
            mother_first_name="Christine",
            mother_last_name="Ravenel",
            father_first_name="Pascal",
            father_last_name="Ravenel",
            registrant_first_name="Florent",
            registrant_last_name="Ravenel",
            persist=True,
        )
    )

    births = list(graph.subjects(RDF.type, BIRTH))
    assert len(births) == 4

    people = {
        str(o)
        for s in graph.subjects(RDF.type, PERSON)
        for o in graph.objects(s, RDFS.label)
    }
    assert people == {
        "Emma Petit",
        "Christine Example",
        "Pascal Example",
        "Alice Dupont",
    }

    assert any(str(o) == "Vitré" for o in graph.objects(None, RDFS.label))
    assert any(str(o) == "1989-12-05" for o in graph.objects(None, RDFS.label))

    # One declaration act and one registration per birth registered.
    assert len(list(graph.subjects(RDF.type, DECLARATION))) == 4
    registrations = list(graph.subjects(RDF.type, REGISTRATION))
    assert len(registrations) == 4
    records = list(graph.subjects(RDF.type, BIRTH_RECORD))
    assert len(records) == 4

    assert len(store.graph) == len(graph)


def test_registration_traces_to_the_declarant_through_the_declaration_act():
    """The source hangs off the declaration act, not off the record."""
    pipe, _store = _pipeline()
    graph = pipe.run(
        BirthRegistrationPipelineParameters(
            first_name="Jeremy",
            last_name="Ravenel",
            birth_date="05/12/1989",
            registrant_first_name="Florent",
            registrant_last_name="Ravenel",
            persist=True,
        )
    )

    florent = next(
        s
        for s in graph.subjects(RDF.type, PERSON)
        if any(str(o) == "Alice Dupont" for o in graph.objects(s, RDFS.label))
    )

    for registration in graph.subjects(RDF.type, REGISTRATION):
        # registration → declaration act → agent
        declaration = next(
            graph.objects(registration, PERSONNEL.hasInformationSource)
        )
        assert (declaration, RDF.type, DECLARATION) in graph
        assert (declaration, CCO.ont00001833, florent) in graph
        # the act carries when it was said and what was said
        assert next(graph.objects(declaration, PERSONNEL.declared_content), None)
        # the registration records exactly one birth, and outputs one record
        assert len(list(graph.objects(registration, PERSONNEL.registersBirth))) == 1
        assert len(list(graph.objects(registration, CCO.ont00001829))) == 1


def test_one_birth_survives_two_registrations():
    """Two registrations of the same person share one Birth and chain in order."""
    pipe, store = _pipeline()
    pipe.run(
        BirthRegistrationPipelineParameters(
            first_name="Jeremy",
            last_name="Ravenel",
            registrant_first_name="Florent",
            registrant_last_name="Ravenel",
            persist=True,
        )
    )
    graph = pipe.run(
        BirthRegistrationPipelineParameters(
            first_name="Jeremy",
            last_name="Ravenel",
            mother_first_name="Christine",
            mother_last_name="Ravenel",
            father_first_name="Pascal",
            father_last_name="Ravenel",
            registrant_first_name="Florent",
            registrant_last_name="Ravenel",
            persist=True,
        )
    )

    jeremy = next(
        s
        for s in store.graph.subjects(RDF.type, PERSON)
        if any(str(o) == "Emma Petit" for o in store.graph.objects(s, RDFS.label))
    )
    # The birth is a single mind-independent process however often it is registered.
    assert len(list(store.graph.objects(jeremy, PERSONNEL.hasBirth))) == 1
    birth = next(store.graph.objects(jeremy, PERSONNEL.hasBirth))
    assert len(list(store.graph.subjects(PERSONNEL.registersBirth, birth))) == 2

    assert any(p == PERSONNEL.updatesPriorRegistration for _s, p, _o in graph)
    assert any(p == PERSONNEL.hasMother for _s, p, _o in graph)
    assert any(p == PERSONNEL.hasFather for _s, p, _o in graph)
    assert next(store.graph.objects(birth, PERSONNEL.hasMother), None) is not None
    assert next(store.graph.objects(birth, PERSONNEL.hasFather), None) is not None


def test_names_land_as_data_properties_on_the_person():
    pipe, _store = _pipeline()
    graph = pipe.run(
        BirthRegistrationPipelineParameters(
            first_name="Jeremy",
            last_name="Ravenel",
            registrant_first_name="Florent",
            registrant_last_name="Ravenel",
            persist=False,
        )
    )
    jeremy = next(
        s
        for s in graph.subjects(RDF.type, PERSON)
        if any(str(o) == "Emma Petit" for o in graph.objects(s, RDFS.label))
    )
    assert str(next(graph.objects(jeremy, PERSONNEL.given_name))) == "Jeremy"
    assert str(next(graph.objects(jeremy, PERSONNEL.family_name))) == "Ravenel"


def test_document_source_of_trust():
    """A document source becomes the output of the declaration act, not its agent."""
    pipe, _store = _pipeline()
    graph = pipe.run(
        BirthRegistrationPipelineParameters(
            first_name="Ada",
            last_name="Lovelace",
            source_document_label="Baptism register — Ada Lovelace",
            persist=False,
        )
    )
    docs = list(graph.subjects(RDF.type, DOCUMENT))
    assert len(docs) == 1
    records = list(graph.subjects(RDF.type, BIRTH_RECORD))
    assert len(records) == 1

    declarations = list(graph.subjects(RDF.type, DECLARATION))
    assert len(declarations) == 1
    assert (declarations[0], CCO.ont00001829, docs[0]) in graph
    assert not list(graph.objects(declarations[0], CCO.ont00001833))


def test_as_tools_exposes_register_birth():
    pipe, _store = _pipeline()
    tools = pipe.as_tools()
    assert len(tools) == 1
    assert tools[0].name == "register_birth"
