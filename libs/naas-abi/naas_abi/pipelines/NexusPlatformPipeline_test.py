from unittest.mock import MagicMock

import pytest
from naas_abi.pipelines.NexusPlatformPipeline import (
    NexusPlatformPipeline,
    NexusPlatformPipelineConfiguration,
    NexusPlatformPipelineParameters,
)
from rdflib import Dataset, Graph, Literal, URIRef
from rdflib.namespace import RDF, RDFS

NEXUS = 'http://ontology.naas.ai/nexus/'
CATALOG = URIRef('http://ontology.naas.ai/graph/nexus')


class CatalogStore:
    def __init__(self):
        self.dataset = Dataset()

    def query(self, query):
        return self.dataset.query(query)

    def list_graphs(self):
        return [graph.identifier for graph in self.dataset.graphs() if len(graph)]

    def remove(self, graph, graph_name):
        for triple in graph:
            self.dataset.graph(graph_name).remove(triple)


@pytest.mark.parametrize('fails', [False, True])
def test_rebuild_keeps_ownership_empty_graph_labels_and_roles_even_on_failure(monkeypatch, fails):
    store = CatalogStore()
    catalog = store.dataset.graph(CATALOG)
    graph = URIRef('http://example.org/daily-observation-graph')
    role = URIRef('http://example.org/personal-role')
    old_agent = URIRef('http://example.org/removed-agent')
    durable = [
        (graph, RDF.type, URIRef(NEXUS + 'KnowledgeGraph')),
        (graph, URIRef(NEXUS + 'graphWorkspaceId'), Literal('workspace-a')),
        (graph, RDFS.label, Literal('My dated graph')),
        (graph, URIRef(NEXUS + 'hasKnowledgeGraphRole'), role),
        (role, RDFS.label, Literal('Research')),
    ]
    for triple in durable:
        catalog.add(triple)
    catalog.add((old_agent, RDF.type, URIRef(NEXUS + 'Agent')))
    pipeline = NexusPlatformPipeline(NexusPlatformPipelineConfiguration(
        triple_store=store, object_storage=MagicMock(), force_update=True))
    monkeypatch.setattr(pipeline, '_compute_signature', lambda: 'changed')
    monkeypatch.setattr(pipeline, '_write_signature', lambda _: None)
    monkeypatch.setattr(pipeline, 'initialize_nexus_graphs', lambda: Graph())

    def agents():
        if fails:
            raise RuntimeError('Simulated later bootstrap failure')
        return Graph()

    monkeypatch.setattr(pipeline, 'initialize_nexus_agents', agents)
    if fails:
        with pytest.raises(RuntimeError, match='later bootstrap'):
            pipeline.run(NexusPlatformPipelineParameters())
    else:
        pipeline.run(NexusPlatformPipelineParameters())
    assert all(triple in catalog for triple in durable)
    assert not list(catalog.triples((old_agent, None, None)))
