from contextlib import contextmanager

from naas_abi_core.services.triple_store.TripleStorePorts import QueryStream
from rdflib import OWL, RDF, URIRef

from naas_abi_marketplace.domains.operations.modules.ontology_engineer.workflows.EntityResolutionWorkflow import (
    EntityResolutionWorkflow,
    EntityResolutionWorkflowConfiguration,
)

TRIPLES = [
    (URIRef("urn:a"), RDF.type, OWL.NamedIndividual),
    (URIRef("urn:b"), RDF.type, OWL.Class),
]


class _Store:
    """Streams only: a materialized query fails the test."""

    def query(self, sparql):
        raise AssertionError("graphs are loaded from query_stream")

    @contextmanager
    def query_stream(self, sparql):
        yield QueryStream("CONSTRUCT", triples=iter(TRIPLES))


def test_schema_and_individuals_load_from_streams():
    workflow = EntityResolutionWorkflow(
        EntityResolutionWorkflowConfiguration(triple_store=_Store())
    )

    assert set(workflow._load_schema_from_triplestore()) == set(TRIPLES)
    assert set(workflow._load_individuals_from_triplestore()) == set(TRIPLES)
