"""What every markets pipeline shares: where it writes, and how it persists."""

from __future__ import annotations

from dataclasses import dataclass

from naas_abi_core.pipeline import PipelineConfiguration
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.utils.graph_builders import (
    DEFAULT_GRAPH_NAME,
    MarketGraphContext,
)
from rdflib import Graph, URIRef


@dataclass
class MarketPipelineConfiguration(PipelineConfiguration):
    triple_store: TripleStoreService | None = None
    graph_name: URIRef = URIRef(DEFAULT_GRAPH_NAME)
    persist: bool = True
    # Pass one context to several pipelines to build one graph for a batch (the
    # seed does); each run then returns only the triples it added.
    context: MarketGraphContext | None = None


def run_in_context(configuration: MarketPipelineConfiguration, build) -> Graph:
    """Run ``build(context)``, persist what it added, and return it.

    A pipeline that owns its context returns the whole graph it built; one
    sharing a context returns only its own delta.
    """
    owned = configuration.context is None
    context = configuration.context or MarketGraphContext()
    before = set(context.graph)
    build(context)
    delta = Graph()
    delta.bind("abi", "http://ontology.naas.ai/abi/")
    for triple in context.graph:
        if triple not in before:
            delta.add(triple)
    if configuration.persist and configuration.triple_store is not None and len(delta):
        configuration.triple_store.insert(delta, graph_name=configuration.graph_name)
    return context.graph if owned else delta
