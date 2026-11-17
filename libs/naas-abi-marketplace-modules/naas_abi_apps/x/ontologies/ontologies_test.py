"""The X ontologies: what the SDK sends to the schema graph, and the generated
classes on the vendored ABI base classes."""

from __future__ import annotations

from pathlib import Path

from naas_abi_apps.common.testing import no_core_import
from naas_abi_apps.x.ontologies.modules import ABIBase
from naas_abi_apps.x.ontologies.modules.XOntology import TweetLanguage, XUser
from naas_abi_apps.x.ontologies.processes.XSearchRecentTweetsProcess import (
    SearchRecentTweets,
)
from naas_abi_sdk.ontologies import schema_source
from rdflib import OWL, RDF, RDFS, Graph, Literal, URIRef

ONTOLOGIES = Path(__file__).parent
TTL = [
    "modules/XOntology.ttl",
    "processes/XCountRecentTweetsProcess.ttl",
    "processes/XSearchRecentTweetsProcess.ttl",
    "queries/XSparqlQueries.ttl",
]


def test_every_ttl_file_parses_and_has_a_name_the_engine_accepts() -> None:
    found = sorted(str(p.relative_to(ONTOLOGIES)) for p in ONTOLOGIES.rglob("*.ttl"))
    assert found == TTL
    for name in found:
        assert schema_source("applications.x", name) == f"module/applications.x/{name}"
        assert len(Graph().parse(ONTOLOGIES / name, format="turtle")) > 0


def test_the_classes_import_neither_core_nor_naas_abi() -> None:
    assert (
        no_core_import(
            "naas_abi_apps.x.ontologies.modules.XOntology",
            "naas_abi_apps.x.ontologies.processes.XSearchRecentTweetsProcess",
            "naas_abi_apps.x.ontologies.processes.XCountRecentTweetsProcess",
        )
        is None
    )


def test_the_x_classes_build_on_the_vendored_bases() -> None:
    assert issubclass(XUser, ABIBase.GenericallyDependentContinuant)
    assert issubclass(TweetLanguage, ABIBase.Quality)
    assert issubclass(SearchRecentTweets, ABIBase.Process)


def test_an_individual_gives_the_triples_it_always_gave() -> None:
    tweet = URIRef("http://ontology.naas.ai/x/Tweet/1")
    language = TweetLanguage(
        _uri="http://ontology.naas.ai/x/TweetLanguage/en",
        label="Tweet language en",
        language_code="en",
        inheresIn=[tweet],
    )
    subject = URIRef(language._uri)

    assert set(language.rdf()) == {
        (subject, RDF.type, URIRef("http://ontology.naas.ai/x/TweetLanguage")),
        (subject, RDF.type, OWL.NamedIndividual),
        (subject, RDFS.label, Literal("Tweet language en")),
        (subject, URIRef("http://ontology.naas.ai/x/lang"), Literal("en")),
        (subject, URIRef("http://ontology.naas.ai/abi/inheresIn"), tweet),
    }

    instant = ABIBase.TemporalInstant(
        _uri="http://ontology.naas.ai/x/TemporalInstant/t", label="t"
    )
    graph = instant.rdf()
    assert (
        URIRef(instant._uri),
        RDF.type,
        URIRef("http://ontology.naas.ai/abi/TemporalInstant"),
    ) in graph
