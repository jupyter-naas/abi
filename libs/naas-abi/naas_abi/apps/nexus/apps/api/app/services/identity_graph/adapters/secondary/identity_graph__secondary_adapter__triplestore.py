from __future__ import annotations

from collections.abc import Callable, Iterator

from naas_abi.apps.nexus.apps.api.app.services.identity_graph.port import (
    IdentityGraphStorePort,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from rdflib import Graph, URIRef

# Triples per insert. A whole snapshot in one call (100k+ triples on an install with
# 100+ workspaces: one agent row per agent per workspace) outlasts the triple store
# request's deadline over NATS, and the sync's retries start over each time.
BATCH_SIZE = 2000


class IdentityGraphStoreSecondaryAdapterTripleStore(IdentityGraphStorePort):
    """Rebuilds the identity named graph: drop, then insert, ``batch_size`` triples at a time.

    Dropping first is what drops users and memberships deleted in Postgres
    since the last boot. ``DROP SILENT`` is a no-op if the graph is missing,
    and avoids ``list_graphs()`` + ``CLEAR GRAPH``: Fuseki's catalog can list a
    named graph that ``CLEAR GRAPH`` then rejects with HTTP 400.
    """

    def __init__(
        self,
        triple_store_getter: Callable[[], TripleStoreService],
        *,
        batch_size: int = BATCH_SIZE,
    ):
        self._triple_store_getter = triple_store_getter
        self._batch_size = max(1, batch_size)

    def replace_graph(self, graph_uri: URIRef, graph: Graph) -> None:
        triple_store = self._triple_store_getter()
        triple_store.query(f"DROP SILENT GRAPH <{graph_uri}>")
        for batch in _batches(graph, self._batch_size):
            triple_store.insert(batch, graph_uri)


def _batches(graph: Graph, size: int) -> Iterator[Graph]:
    """``graph`` in graphs of at most ``size`` triples; none for an empty graph."""
    batch = Graph()
    for triple in graph:
        batch.add(triple)
        if len(batch) >= size:
            yield batch
            batch = Graph()
    if len(batch):
        yield batch
