"""Read named graphs from the platform triple store into one rdflib Graph."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from rdflib import Graph, URIRef

SOURCE_CHECKSUM = "http://ontology.naas.ai/abi/sourceChecksum"


class GraphNotFoundError(LookupError):
    """A requested named graph is missing or empty."""


def read_named_graph(triple_store: Any, iri: str) -> Graph:
    result = triple_store.query(
        "CONSTRUCT { ?s ?p ?o } WHERE { "
        f"GRAPH <{iri}> {{ ?s ?p ?o FILTER(?p != <{SOURCE_CHECKSUM}>) }} "
        "}"
    )
    graph = result if isinstance(result, Graph) else result.graph
    if graph is None or not len(graph):
        raise GraphNotFoundError(f"Graph {iri} is missing or empty")
    return graph


def merge_named_graphs(triple_store: Any, iris: Sequence[str]) -> tuple[Graph, list[str]]:
    """Merge every non-empty graph in ``iris``. Returns graphs actually read."""
    merged = Graph()
    read: list[str] = []
    for iri in iris:
        try:
            chunk = read_named_graph(triple_store, iri)
        except GraphNotFoundError:
            continue
        merged += chunk
        read.append(iri)
    if not len(merged):
        raise GraphNotFoundError("No triples in the requested workspace graphs")
    return merged, read
